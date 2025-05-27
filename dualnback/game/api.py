from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ObjectDoesNotExist
from utils import calculate_game_parameters
User = get_user_model()  # <- Lấy CustomUser thay vì mặc định

class RegisterView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=400)
        user = User.objects.create_user(username=username, password=password)
        return Response({"message": "User created"}, status=201)

class LoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            })
        return Response({"error": "Invalid credentials"}, status=401)


from rest_framework.permissions import IsAuthenticated
from .models import GameRoom
import random, string

def generate_room_code():
    return ''.join(random.choices(string.digits, k=4))

class CreateRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = generate_room_code()
        length = request.data.get("length", 20)
        n_back = request.data.get("n_back", 2)
        delay = request.data.get("delay", 3)

        room = GameRoom.objects.create(
            room_code=code,
            host=request.user,
            length=length,
            n_back=n_back,
            delay=delay
        )
        return Response({
            "room_code": room.room_code,
            "length": room.length,
            "n_back": room.n_back,
            "delay": room.delay
        })

from .models import SingleGameRoom
class CreateSingleGameRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Lấy cấp độ từ request hoặc mặc định là 1
        level = request.data.get("level", 1)
        # Tính toán các tham số trò chơi dựa trên cấp độ
        length, n_back, delay = calculate_game_parameters(level)
        if level > request.user.highest_level +1:
            return Response({
                "error": "You cannot create a room with a level higher than your highest level."
            }, status=400)
        # Tạo phòng chơi đơn
        room = SingleGameRoom.objects.create(
            host=request.user,
            level=level,
            host_ready=False,
            host_total_answered=0,
            host_score=0
        )

        return Response({
            "message": "Single game room created successfully",
            "room_id": room.id,
            "level": room.level,
            "length": length,
            "n_back": n_back,
            "delay": delay,
        }, status=201)
class SingleGameReadyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room_id = request.data.get("room_id")
        try:
            # Lấy phòng chơi đơn dựa trên ID và người dùng hiện tại
            room = SingleGameRoom.objects.get(id=room_id, host=request.user)
        except SingleGameRoom.DoesNotExist:
            return Response({"error": "Room not found or you are not the host"}, status=404)

        # Đặt trạng thái ready cho người chơi
        room.host_ready = True
        room.save()

        # Gửi thông báo qua WebSocket để bắt đầu trò chơi
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"single_game_{room.id}",
            {
                "type": "start_game",
                "message": "Game is starting!"
            }
        )

        return Response({"message": "Ready status set, game will start soon"})
class ReadyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("room_code")
        try:
            room = GameRoom.objects.get(room_code=code)
        except GameRoom.DoesNotExist:
            return Response({"error": "Room not found"}, status=404)

        if request.user == room.host:
            room.host_ready = True
        elif request.user == room.guest:
            room.guest_ready = True
        else:
            return Response({"error": "You are not part of this room"}, status=403)

        room.save()

        # Nếu cả hai cùng sẵn sàng → thông báo WebSocket để bắt đầu
        if room.both_ready():
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"game_{room.room_code}",
                {
                    "type": "start_game"
                }
            )

        return Response({"message": "Ready status set"})
class JoinRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("room_code")
        try:
            room = GameRoom.objects.get(room_code=code)
        except GameRoom.DoesNotExist:
            return Response({"error": "Room does not exist"}, status=404)

        if room.guest is not None:
            return Response({"error": "Room is full"}, status=400)

        if room.host == request.user:
            return Response({"error": "You are already the host of this room"}, status=400)

        room.guest = request.user
        room.save()

        return Response({"message": "Joined room successfully"})
def count_correct_positions(sequence, n_back):
    if not isinstance(sequence, list):
        return 0
    count = 0
    for i in range(n_back, len(sequence)):
        if sequence[i]["position"] == sequence[i - n_back]["position"]:
            count += 1
    return count
   
class GameResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_code):
        try:
            room = GameRoom.objects.get(room_code=room_code)
        except GameRoom.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)




        n_back = room.n_back 
        sequence = room.sequence or []
        total_correct_in_sequence = count_correct_positions(sequence, n_back)

        def compute_f1(correct, answered, total_needed):
            precision = correct / answered if answered > 0 else 0
            recall = correct / total_needed if total_needed > 0 else 0
            if precision + recall == 0:
                return 0
            return round(2 * (precision * recall) / (precision + recall) * 100, 2)

        host_f1 = compute_f1(room.host_score, room.host_total_answered, total_correct_in_sequence)
        guest_f1 = compute_f1(room.guest_score, room.guest_total_answered, total_correct_in_sequence)
                # ✅ Tính lại winner
        if host_f1 > guest_f1:
            room.winner = room.host
        elif guest_f1 > host_f1:
            room.winner = room.guest
        else:
            room.winner = None
        room.save()
        return Response({
            "host_score": room.host_score,
            "guest_score": room.guest_score,
            "host_total_answered": room.host_total_answered,
            "guest_total_answered": room.guest_total_answered,
            "total_correct_in_sequence": total_correct_in_sequence,
            "host_percent": host_f1,
            "guest_percent": guest_f1,
            "winner": room.winner.id if room.winner else "draw"
        })
class SingleGameResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        try:
            from .models import SingleGameRoom
            room = SingleGameRoom.objects.get(id=room_id, host=request.user)
        except SingleGameRoom.DoesNotExist:
            return Response({"error": "Room not found or you are not the host"}, status=status.HTTP_404_NOT_FOUND)

        n_back = room.level  
        sequence = room.sequence or []
        total_correct_in_sequence = count_correct_positions(sequence, n_back)

        def compute_f1(correct, answered, total_needed):
            precision = correct / answered if answered > 0 else 0
            recall = correct / total_needed if total_needed > 0 else 0
            if precision + recall == 0:
                return 0
            return round(2 * (precision * recall) / (precision + recall) * 100, 2)

        # ✅ Tính F1 cho host
        host_f1 = compute_f1(room.host_score, room.host_total_answered, total_correct_in_sequence)

        user = request.user
        if host_f1 >= 80:
            if room.level == user.highest_level+1:
                user.highest_level = room.level
                user.f1_of_highest_level = host_f1
                user.save()
            elif room.level == user.highest_level:
                room.level = user.highest_level and host_f1 > user.f1_of_highest_level
                user.f1_of_highest_level = max(user.f1_of_highest_level, host_f1)
                user.save()


        return Response({
            "host_score": room.host_score,
            "host_total_answered": room.host_total_answered,
            "total_correct_in_sequence": total_correct_in_sequence,
            "host_percent": host_f1,
            "highest_level": user.highest_level,
            "f1_of_highest_level": user.f1_of_highest_level
        })
class GetRoomInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_code):
        try:
            room = GameRoom.objects.get(room_code=room_code)
        except ObjectDoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "room_code": room.room_code,
            "status": room.status,
            "n_back": room.n_back,
            "length": room.length,
            "delay": room.delay,
        }, status=200)
class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().order_by('-highest_level', '-f1_of_highest_level')[:10]
        leaderboard = [
            {
                "username": user.username,
                "highest_level": user.highest_level,
                "f1_of_highest_level": user.f1_of_highest_level,
            }
            for user in users
        ]

        return Response({"leaderboard": leaderboard}, status=200)