from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Subscription


class Command(BaseCommand):
    help = "Remove (expire) subscriptions whose renewal date has passed."

    def handle(self, *args, **options):
        today = timezone.now().date()
        expired = Subscription.objects.filter(status="active", renews_at__lt=today)
        count = expired.count()
        for sub in expired.iterator():
            sub.status = "expired"
            sub.renews_at = today
            sub.save()
        if options.get("delete", False):
            Subscription.objects.filter(status="expired").delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired subscription(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Expired {count} subscription(s)."))

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Permanently remove expired subscriptions from the database.",
        )
