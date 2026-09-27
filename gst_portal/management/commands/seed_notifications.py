"""Seed a realistic batch of notifications for a user and push them live.

Run: python manage.py seed_notifications [--user user@example.com] [--count N]

Creates ``--count`` (default 6) notifications spanning every notification type
the gst-app Notifications page filters on (Deadline / Success / Upload /
Warning / Info). Each one goes through ``create_notification`` so it is ALSO
pushed over the WebSocket channel layer -- if the user's browser tab is open,
the header badge updates live as the command runs.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gst_portal.services import create_notification

User = get_user_model()

SAMPLE_NOTIFICATIONS = [
    {
        "title": "GSTR-3B Due Alert",
        "message": "GSTR-3B is due in 3 days for ABC Corp (GSTIN: 27AAACC1001Z1). "  # noqa: E501
        "File immediately to avoid late fees.",
        "notification_type": "Deadline",
    },
    {
        "title": "GSTR-7 Filed Successfully",
        "message": "GSTR-7 for last month has been reconciled and filed successfully.",
        "notification_type": "Success",
    },
    {
        "title": "New Voucher Uploaded",
        "message": "A new purchase voucher has been uploaded to your documents.",
        "notification_type": "Upload",
    },
    {
        "title": "Missing Documents",
        "message": "3 invoices unmatched in ITC reconciliation. Please review them.",
        "notification_type": "Warning",
    },
    {
        "title": "Monthly Report Ready",
        "message": "Your GST compliance report for the previous month is ready.",
        "notification_type": "Info",
    },
    {
        "title": "Welcome to SmartGST",
        "message": "Your portal is now backed by the live Django backend.",
        "notification_type": "Info",
    },
]


class Command(BaseCommand):
    help = "Seed sample notifications for a user and push them over the WebSocket."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            default="",
            help="Target user email (default: first active non-staff user).",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=len(SAMPLE_NOTIFICATIONS),
            help="How many notifications to create (default: all samples).",
        )

    def handle(self, *args, **options):
        count = options.get("count") or len(SAMPLE_NOTIFICATIONS)
        target = (options.get("user") or "").strip()

        if target:
            user = User.objects.filter(email=target).first()
            if user is None:
                self.stdout.write(self.style.ERROR(f"No user found with email {target}."))
                return
        else:
            user = User.objects.filter(is_active=True, is_staff=False).order_by("pk").first()
            if user is None:
                self.stdout.write(self.style.ERROR("No active non-staff user found."))
                return

        samples = (SAMPLE_NOTIFICATIONS * (count // len(SAMPLE_NOTIFICATIONS) + 1))[:count]
        created = []
        for sample in samples:
            n = create_notification(user=user, **sample)
            created.append(n.pk)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [{n.notification_type:8s}] {n.title} (id={n.pk}) -> live push sent"
                )
            )

        unread = user.gst_notifications.filter(is_read=False).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {len(created)} notification(s) created for "
                f"{user.email} (unread now: {unread})."
            )
        )
