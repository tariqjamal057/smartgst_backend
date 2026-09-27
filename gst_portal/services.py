"""Notification helpers usable from the Django server AND Celery tasks."""

from .models import Notification
from .serializers import NotificationSerializer


def create_notification(user, title, message="", notification_type="Info", broadcast=True):
    """Create an in-app Notification and (optionally) push it over the channel layer.

    Safe to call from a normal Django request/command (sync) and from a Celery
    worker (sync task). ``broadcast=False`` creates the row without pushing.
    """
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message or "",
        notification_type=notification_type or "Info",
    )
    if broadcast:
        push_notification(user.pk, NotificationSerializer(notification).data)
    return notification


def push_notification(user_id, payload):
    """Send ``notification_created`` to every socket of ``user_id``.

    Uses ``async_to_sync`` so it works from synchronous code (views, commands,
    Celery tasks). No-ops silently if the channel layer is unavailable.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return False
        async_to_sync(layer.group_send)(
            f"notify_user_{user_id}",
            {
                "type": "notification_created",
                "notification": payload,
            },
        )
        return True
    except Exception:
        # A failed push must never break the code that created the notification.
        return False
