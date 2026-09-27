"""Send a single live notification to a user over the WebSocket.

Run: python manage.py notify_test user@example.com "Your title" [message] [type]

Useful for instantly verifying the whole pipeline (row created + channel-layer
push) without touching any real business flow.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gst_portal.services import create_notification

User = get_user_model()


class Command(BaseCommand):
    help = "Send a single live notification to a user over the WebSocket."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Target user email.")
        parser.add_argument("title", help="Notification title.")
        parser.add_argument("message", nargs="?", default="", help="Notification body.")
        parser.add_argument(
            "notification_type",
            nargs="?",
            default="Info",
            help="One of Info / Success / Warning / Deadline / Upload.",
        )

    def handle(self, *args, **options):
        user = User.objects.filter(email=options["email"]).first()
        if user is None:
            self.stdout.write(self.style.ERROR("No such user."))
            return

        created = create_notification(
            user=user,
            title=options["title"],
            message=options["message"],
            notification_type=options["notification_type"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Notification #{created.pk} sent for {user.email} "
                f"(type={created.notification_type})."
            )
        )
