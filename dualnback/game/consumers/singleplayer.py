import json
import ast
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import random
import string
def generate_dual_nback_sequence(length, n_back):
    if length <= n_back:
        raise ValueError("length must be greater than n_back")

    sequence = []
    for _ in range(length):
        position = [random.randint(0, 2), random.randint(0, 2)]
        sequence.append({"position": position})

    # Bắt buộc có ít nhất 1 cặp đúng tại vị trí i (i >= n_back)
    i = random.randint(n_back, length - 1)
    sequence[i]["position"] = sequence[i - n_back]["position"]

    return sequence
class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from django.contrib.auth.models import AnonymousUser
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'game_{self.room_code}'
        self.user = self.scope["user"]

        if self.user == AnonymousUser():
            await self.close()
            return

        room = await self.join_room()
        if not room:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Gửi trạng thái hiện tại về client
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "ready_status",
                "host_ready": room.host_ready,
                "guest_ready": room.guest_ready,
            }
        )


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # async def receive(self, text_data):
    #     data = json.loads(text_data)
    #     # Bạn có thể xử lý dữ liệu từ client ở đây nếu cần
    #     pass
    async def ready_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "ready_status",
            "host_ready": event["host_ready"],
            "guest_ready": event["guest_ready"]
        }))

    @database_sync_to_async
    def is_host(self, room):
        return self.user.id == room.host_id
    @database_sync_to_async
    def join_room(self):
        from ..models import GameRoom

        try:
            room = GameRoom.objects.get(room_code=self.room_code)
        except GameRoom.DoesNotExist:
            return None

        if room.host == self.user or room.guest == self.user:
            return room

        if room.guest is None:
            room.guest = self.user
            room.save()
            return room

        return None
    @database_sync_to_async
    def update_score(self, position_match, correct):
        from ..models import GameRoom
        room = GameRoom.objects.get(room_code=self.room_code)

        print(f"[UPDATE_SCORE] {self.user.username} - pos_match: {position_match}, correct: {correct}")

        if self.user.id == room.host_id:
            if position_match:
                room.host_total_answered += 1
                if correct:
                    room.host_score += 1
        elif self.user.id == room.guest_id:
            if position_match:
                room.guest_total_answered += 1
                if correct:
                    room.guest_score += 1

        room.save()

    @database_sync_to_async
    def get_usernames(self, room):
        return room.host.username, room.guest.username
    @database_sync_to_async
    def mark_user_ready(self):
        from ..models import GameRoom
        room = GameRoom.objects.get(room_code=self.room_code)

        if self.user.id == room.host_id:
            room.host_ready = True
        elif self.user.id == room.guest_id:
            room.guest_ready = True

        room.save()
        return room.host_ready, room.guest_ready
    async def start_sequence(self, event):  
        from ..models import GameRoom
        room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)
        sequence = event["sequence"]
        for step, item in enumerate(sequence):
            await self.send(text_data=json.dumps({
                "type": "step",
                "step": step,
                "data": item
            }))
            await asyncio.sleep(room.delay)

        await asyncio.sleep(3)  # Đợi phản hồi cuối cùng
        room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)

        # ✅ Chỉ host mới gửi kết quả
        if await self.is_host(room):
            await database_sync_to_async(room.set_winner)()

            # 🔁 Tải lại bản mới nhất từ DB
            room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)

            print("diem:", room.host_score, room.guest_score, room.host_total_answered, room.guest_total_answered)
            
            host_percent = (
                room.host_score / room.host_total_answered * 100 if room.host_total_answered > 0 else 0
            )
            guest_percent = (
                room.guest_score / room.guest_total_answered * 100 if room.guest_total_answered > 0 else 0
            )
            # await asyncio.sleep(6)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "game_over",
                    "room_code": room.room_code
                    # "host_percent": round(host_percent, 2),
                    # "guest_percent": round(guest_percent, 2),
                    # "winner": room.winner.username if room.winner else "draw"
                }
            )
            await asyncio.sleep(2)  # Cho client thời gian nhận kết quả
            # await self.reset_room_state()
            
            

    async def send_steps_to_group(self, sequence):
        from ..models import GameRoom
        room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)
        for step, item in enumerate(sequence):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "send_step_to_clients",
                    "step": step,
                    "data": item
                }
            )
            await asyncio.sleep(room.delay)

        await asyncio.sleep(2)  # đợi lượt cuối cùng

        from ..models import GameRoom
        room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)
        await asyncio.sleep(3)
        await database_sync_to_async(room.set_winner)()

        host_percent = (
            room.host_score / room.host_total_answered * 100 if room.host_total_answered > 0 else 0
        )
        guest_percent = (
            room.guest_score / room.guest_total_answered * 100 if room.guest_total_answered > 0 else 0
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "game_over",
                "room_code": room.room_code
                # "host_percent": round(host_percent, 2),
                # "guest_percent": round(guest_percent, 2),
                # "winner": room.winner.username if room.winner else "draw"
            }
        )
        await self.reset_room_state()
    async def start_game(self, event):
        from ..models import GameRoom
        room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)
        # host_username, guest_username = await self.get_usernames(room)


       
        await asyncio.sleep(1)

        # 👇 Chỉ host mới chạy phần gửi step
        if await self.is_host(room):
            sequence = generate_dual_nback_sequence(length=room.length, n_back=room.n_back)
            room.sequence = sequence
            await database_sync_to_async(room.save)()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "start_sequence",
                    "sequence": sequence
                }
            )
   
    async def send_step_to_clients(self, event):
        await self.send(text_data=json.dumps({
            "type": "step",
            "step": event["step"],
            "data": event["data"]
        }))
    @database_sync_to_async
    def is_host_user(self, room):
        return self.user == room.host
    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get("type") == "ready":
            from ..models import GameRoom
            room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)

            # Đặt trạng thái ready
            if self.user.id == room.host_id:
                room.host_ready = True
            elif self.user.id == room.guest_id:
                room.guest_ready = True

            await database_sync_to_async(room.save)()

            # ⚠️ TẢI LẠI room từ DB để có giá trị mới nhất
            room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "ready_status",
                    "host_ready": room.host_ready,
                    "guest_ready": room.guest_ready,
                }
            )

            if room.host_ready and room.guest_ready:
                # await asyncio.sleep(4)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "start_game"
                    }
                )
            return


        
        if data.get("type") == "answer":
            step = data.get("step")
            position_match = data.get("position_match", False)

            from ..models import GameRoom
            room = await database_sync_to_async(GameRoom.objects.get)(room_code=self.room_code)
            # sequence = room.sequence
            # if isinstance(sequence, str):
            #     try:
            #         sequence = json.loads(sequence)
            #     except Exception as e:
            #         print(f"[ERROR] Failed to load sequence: {e}")
            #         return
            sequence = room.sequence or []
            n_back = room.n_back  # hoặc room.difficulty
            # print(f"[DEBUG] Answer received for step {step}, sequence len = {len(sequence)}")
            # print(f"[DEBUG] sequence = {sequence}")
            # ✅ Kiểm tra giới hạn để tránh IndexError
            if not isinstance(sequence, list) or step is None or step >= len(sequence) or step < n_back:
                print(f"[WARNING] Invalid step received: {step} (len: {len(sequence)})")
                return

            current = sequence[step]["position"]
            compare = sequence[step - n_back]["position"]
            print("cur " , current)
            print("com " , compare)
            match = current == compare
            print("mat ",match)
            correct = match and position_match
            print("cor ",correct)
            if self.user.id in [room.host_id, room.guest_id]:
                await self.update_score(position_match, correct)
            return

            # Nếu là bước cuối cùng → tính người thắng
            # if step == len(sequence) - 1:
            #     await database_sync_to_async(room.set_winner)()

            #     # Gửi kết quả cho cả hai người chơi
            #     await self.channel_layer.group_send(
            #         self.room_group_name,
            #         {
            #             "type": "game_over",
            #             "host_score": room.host_score,
            #             "guest_score": room.guest_score,
            #             "winner": room.winner.username if room.winner else "draw"
            #         }
     
    @database_sync_to_async
    def reset_room_state(self):
        from ..models import GameRoom
        room = GameRoom.objects.get(room_code=self.room_code)
        room.host_ready = False
        room.guest_ready = False
        room.sequence = []
        room.host_score = 0
        room.guest_score = 0
        room.host_total_answered = 0
        room.guest_total_answered = 0
        room.winner = None
        room.save()     
    @database_sync_to_async
    def leave_room(self):
        from ..models import GameRoom
        try:
            room = GameRoom.objects.get(room_code=self.room_code)

            if room.host == self.user:
                room.host = None
            elif room.guest == self.user:
                room.guest = None

            # if room.host is None and room.guest is None:
            #     room.delete()
            # else:
            room.save()
        except GameRoom.DoesNotExist:
            pass

    async def disconnect(self, close_code):
        await self.leave_room()
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    async def game_over(self, event):
        await self.send(text_data=json.dumps({
            "type": "game_over",
            "room_code": event.get("room_code")
            # "host_percent": event["host_percent"],
            # "guest_percent": event["guest_percent"],
            # "winner": event["winner"]
        }))