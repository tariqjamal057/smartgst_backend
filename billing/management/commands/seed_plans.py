from django.core.management.base import BaseCommand

from billing.models import Plan


class Command(BaseCommand):
    help = "Seed the default billing plans."

    def handle(self, *args, **options):
        plans = [
            ("Starter", "9999", "10", "2", "Email", 1),
            ("Professional", "24999", "50", "12", "Priority", 2),
            ("Enterprise", "59999", "Unlimited", "12", "Dedicated", 3),
        ]
        for name, price, clients, users, support, order in plans:
            obj, created = Plan.objects.update_or_create(
                name=name,
                defaults={
                    "price": price,
                    "clients": clients,
                    "users": users,
                    "support": support,
                    "sort_order": order,
                    "is_active": True,
                },
            )
            self.stdout.write(self.style.SUCCESS(("Created " if created else "Updated ") + name))
