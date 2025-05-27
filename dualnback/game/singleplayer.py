import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from utils import generate_dual_nback_sequence, calculate_game_parameters

class SingleGameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Lấy room_id từ URL
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f"single_game_{self.room_id}"
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
        # Từ chối kết nối nếu người dùng không xác thực
            await self.close()
            return
            # Thêm client vào group WebSocket
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Xóa client khỏi group WebSocket
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    async def ready_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "ready_status",
            "host_ready": event["host_ready"]
        }))

        # Nếu host đã sẵn sàng, bắt đầu trò chơi
        if event["host_ready"]:
            await self.start_game()


    @database_sync_to_async
    def update_score_single(self, position_match, correct):
        from .models import SingleGameRoom
        room = SingleGameRoom.objects.get(id=self.room_id)

        print(f"[UPDATE_SCORE_SINGLE] {self.user.username} - pos_match: {position_match}, correct: {correct}")

        if position_match:
            room.host_total_answered += 1
            if correct:
                room.host_score += 1

        room.save()
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data.get("type") == "ready":
            # Đánh dấu trạng thái host_ready
            room = await self.get_room()
            room.host_ready = True
            await database_sync_to_async(room.save)()

            # Gửi trạng thái ready về client
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "ready_status",
                    "host_ready": room.host_ready
                }
            )
        if data.get("type") == "answer":
            step = data.get("step")
            position_match = data.get("position_match", False)

            room = await self.get_room()
            sequence = room.sequence or []
            n_back = room.level  # Sử dụng level làm n-back

            # Kiểm tra giới hạn để tránh IndexError
            if not isinstance(sequence, list) or step is None or step >= len(sequence) or step < n_back:
                print(f"[WARNING] Invalid step received: {step} (len: {len(sequence)})")
                return

            current = sequence[step]["position"]
            compare = sequence[step - n_back]["position"]
            match = current == compare
            correct = match and position_match

            # Cập nhật điểm số
            await self.update_score_single(position_match, correct)

    async def start_game(self):
        room = await self.get_room()
        length, n_back, delay = calculate_game_parameters(room.level)
        # Sinh sequence dựa trên level của phòng
        sequence = generate_dual_nback_sequence(length=length, n_back=n_back)

        await self.save_sequence(sequence)

        # Gửi từng bước của sequence đến client
        for step, item in enumerate(sequence):
            await self.send(text_data=json.dumps({
                "type": "step",
                "step": step,
                "data": item
            }))
            await asyncio.sleep(delay)  
        # Gửi thông báo kết thúc sequence
        await self.send(text_data=json.dumps({
            "type": "end_sequence",
            "message": "Sequence completed. Waiting for your response."
        }))

    @database_sync_to_async
    def get_room(self):
        from .models import SingleGameRoom
        # Lấy phòng từ database
        return SingleGameRoom.objects.get(id=self.room_id)

    @database_sync_to_async
    def save_sequence(self, sequence):
        # Lưu sequence vào phòng
        from .models import SingleGameRoom
        room = SingleGameRoom.objects.get(id=self.room_id)
        room.sequence = sequence
        room.save()