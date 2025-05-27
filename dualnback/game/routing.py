from django.urls import re_path
from game import consumers
from game import singleplayer

websocket_urlpatterns = [
    re_path(r'ws/room/(?P<room_code>\w+)/$', consumers.GameConsumer.as_asgi()),
    re_path(r'ws/single-game/(?P<room_id>\d+)/$', singleplayer.SingleGameConsumer.as_asgi()),
]