"""WebSocket consumer that streams live notifications to a logged-in user."""

from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken, TokenError

User = get_user_model()

INVALID_TOKEN_CLOSE_CODE = 4001


def _group_name(user_id) -> str:
    return f"notify_user_{user_id}"


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Push ``notification.new`` events to a single user's browser tab(s)."""

    async def connect(self):
        raw_qs = self.scope.get("query_string", b"").decode("latin-1")
        token = (parse_qs(raw_qs).get("token") or [""])[0]
        user = await self._auth_user(token)
        if user is None or not user.is_active:
            await self.close(code=INVALID_TOKEN_CLOSE_CODE)
            return

        self.user = user
        self.group_name = _group_name(user.pk)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def notification_created(self, event):
        await self.send_json(
            {
                "type": "notification.new",
                "notification": event.get("notification"),
            }
        )

    async def _auth_user(self, token):
        if not token:
            return None
        try:
            access = AccessToken(token)
        except (TokenError, TypeError, ValueError):
            return None

        from asgiref.sync import sync_to_async

        get_user = sync_to_async(User.objects.get, thread_sensitive=True)
        try:
            return await get_user(pk=access.get("user_id"))
        except User.DoesNotExist:
            return None
