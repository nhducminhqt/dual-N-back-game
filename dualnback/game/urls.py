from django.urls import path
from .api import RegisterView, LoginView, CreateRoomView, JoinRoomView, ReadyView, GameResultView,GetRoomInfoView,CreateSingleGameRoomView,SingleGameResultView,LeaderboardView

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("create-single-game-room/", CreateSingleGameRoomView.as_view()),
    path("create-room/", CreateRoomView.as_view()),
    path("join-room/", JoinRoomView.as_view()),
    path("api/ready/", ReadyView.as_view()),
    path("game-result/<str:room_code>/", GameResultView.as_view()),
    path('room/<str:room_code>/', GetRoomInfoView.as_view(), name='get_room_info'),
    path('single-game-result/<int:room_id>/', SingleGameResultView.as_view(), name='get_room_result'),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),]