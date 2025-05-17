from django.urls import re_path
from .consumers import consumers

websocket_urlpatterns = [
    re_path(r'ws/room/(?P<room_code>\w+)/$', consumers.GameConsumer.as_asgi()),
]
