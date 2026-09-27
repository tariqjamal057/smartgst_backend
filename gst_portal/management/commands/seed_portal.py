"""Seed demo users, firms and clients for the gst-app portal.

Run with::

    python manage.py seed_portal

Creates:
  * demo admin (staff) + superadmin + regular user
  * a handful of CA firms and GST clients
  * sample reminders and an initial notification
"""

import secrets
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gst_portal.models import Firm, GSTClient, Reminder
from gst_portal.services import create_notification

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo users, firms and clients for the gst-app portal."

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(
            email="admin@smartgst.com",
            defaults={
                "first_name": "Admin",
                "last_name": "User",
            },
        )
        admin.is_staff = True
        admin.set_password("Admin@123")
        admin.save()

        super_usr, _ = User.objects.get_or_create(
            email="superadmin@smartgst.com",
            defaults={
                "first_name": "Super",
                "last_name": "Admin",
            },
        )
        super_usr.is_staff = True
        super_usr.is_superuser = True
        super_usr.set_password("Super@123")
        super_usr.save()

        user, _ = User.objects.get_or_create(
            email="demo@smartgst.com",
            defaults={"first_name": "Demo", "last_name": "User"},
        )
        user.set_password("Demo@123")
        user.save()

        self.stdout.write(
            self.style.SUCCESS(f"Users ready: {admin.email}, {super_usr.email}, {user.email}")
        )

        firm_data = [
            ("Sharma & Co", "Pro"),
            ("Gupta Associates", "Enterprise"),
            ("Rajeshwari Tax", "Pro"),
            ("Verma Consultants", "Basic"),
            ("Singh Brothers", "Pro"),
            ("Patel Advisors", "Basic"),
        ]
        firms = {}
        for name, plan in firm_data:
            firm_pk, created = Firm.objects.update_or_create(
                name=name,
                defaults={
                    "email": name.lower().replace(" & ", ".").replace(" ", "") + "@smartgst.com",
                    "plan": plan,
                    "api_key": secrets.token_hex(8),
                    "password": uuid.uuid4().hex,
                    "is_active": True,
                    "reg_date": date.today() - timedelta(days=90),
                },
            )
            firms[name] = firm_pk
            if created:
                self.stdout.write(f"  created firm {name}")

        client_data = [
            ("Acme Industries", "33ABCDE1234F1Z5", "Tamil Nadu"),
            ("Sunrise Traders", "27AAECS1234G1Z4", "Maharashtra"),
            ("Sharma Retail", "07AAECS1234H1Z2", "Delhi"),
            ("TechNova Pvt Ltd", "24AAGCT1234J1Z6", "Gujarat"),
        ]
        for idx, (name, gstin, state) in enumerate(client_data):
            firm_name = list(firms)[idx % len(list(firms))]
            GSTClient.objects.update_or_create(
                name=name,
                defaults={
                    "owner": user,
                    "firm": firms[firm_name],
                    "gstin": gstin,
                    "mobile": f"98{idx:08d}",
                    "email": name.lower().replace(" ", "") + "@example.com",
                    "state": state,
                    "reg_date": date.today() - timedelta(days=30),
                },
            )

        Reminder.objects.get_or_create(
            user=user,
            title="GSTR-1 filing due (August)",
            defaults={"date": date.today() + timedelta(days=9), "is_done": False},
        )
        Reminder.objects.get_or_create(
            user=user,
            title="GSTR-3B filing due (August)",
            defaults={"date": date.today() + timedelta(days=19), "is_done": False},
        )
        create_notification(
            user=user,
            title="Welcome to SmartGST",
            message="Your portal is now backed by the live Django backend.",
            notification_type="Info",
        )

        from gst_portal.models import ApiCallLog

        if ApiCallLog.objects.count() == 0:
            ApiCallLog.objects.create(
                user=super_usr,
                endpoint="search:33CGFPA6633Q4Z4",
                method="GET",
                gstin="33CGFPA6633Q4Z4",
                status="Success",
                time_taken_ms=612,
            )
            ApiCallLog.objects.create(
                user=super_usr,
                endpoint="returns",
                method="GET",
                gstin="33CGFPA6633Q4Z4",
                status="Success",
                time_taken_ms=902,
            )

        self.stdout.write(self.style.SUCCESS("Seed data ready."))
