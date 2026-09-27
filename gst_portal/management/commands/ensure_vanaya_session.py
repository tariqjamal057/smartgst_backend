"""Login once per sandbox GSTN credential and cache the session.

Run: python manage.py ensure_vanaya_session [--otp 575757]

Establishes a cached session (auth_token + raw app key + dek) for every
credential in ``VANAYA_CREDENTIALS``. Subsequent API calls reuse the cached
session (no new OTP / no new session slot) until it expires.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from vanaya.services import VanayaClient


class Command(BaseCommand):
    help = "Warm up cached Vanaya sessions for all sandbox credentials."

    def add_arguments(self, parser):
        parser.add_argument("--otp", default=None, help="Override the default OTP.")

    def handle(self, *args, **options):
        otp = options.get("otp") or settings.VANAYA_DEFAULT_OTP
        pool = list(getattr(settings, "VANAYA_CREDENTIALS", []) or [])
        if not pool:
            self.stdout.write(self.style.ERROR("VANAYA_CREDENTIALS is not configured."))
            return

        for cred in pool:
            gstin = cred.get("gstin") or settings.VANAYA_GSTIN
            client = VanayaClient(
                gstin=gstin,
                username=cred.get("username") or settings.VANAYA_USERNAME,
                state_code=cred.get("state_code") or settings.VANAYA_STATE_CODE,
            )
            if client.get_auth_token():
                self.stdout.write(
                    self.style.SUCCESS(f"{gstin} ({client.username}): session cached, reusing.")
                )
                continue
            try:
                client.send_otp()
                body = client.authenticate(otp=otp)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{gstin} ({client.username}): authenticated, session cached "
                        f"(expiry={body.get('expiry')} mins)."
                    )
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"{gstin} ({client.username}): {exc}"))
