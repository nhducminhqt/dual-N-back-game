from urllib.parse import parse_qs


from jwt import decode as jwt_decode
from django.conf import settings
from asgiref.sync import sync_to_async

@sync_to_async
def get_user(user_id):
    from game.models import CustomUser
    from django.contrib.auth.models import AnonymousUser
    try:
        return CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return AnonymousUser()

class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework_simplejwt.tokens import UntypedToken
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token", [None])[0]

        if token is None:
            scope["user"] = AnonymousUser()
        else:
            try:
                UntypedToken(token)
                decoded = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                scope["user"] = await get_user(decoded["user_id"])
            except Exception:
                scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)
