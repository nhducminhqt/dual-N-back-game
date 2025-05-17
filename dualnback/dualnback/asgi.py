"""
ASGI config for dualnback project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import game.routing
from game.middleware import JWTAuthMiddleware 
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dualnback.settings")


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(
            game.routing.websocket_urlpatterns
        )
    ),
})
