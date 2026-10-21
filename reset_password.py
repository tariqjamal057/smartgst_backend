#!/usr/bin/env python
"""Reset a user's password from the command line.

Usage:
    python reset_password.py <email> [--password PASSWORD] [--deactivate]

If --password is omitted a strong temporary password is generated and printed.
"""
import argparse
import os
import secrets
import string
import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent


def generate_password(length=14):
    """Build a strong temporary password containing mixed case, digits and symbols."""
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%^&*"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        checks = (
            any(c.isupper() for c in candidate),
            any(c.islower() for c in candidate),
            any(c.isdigit() for c in candidate),
            any(c in "!@#$%^&*" for c in candidate),
        )
        if all(checks):
            return candidate


def main():
    parser = argparse.ArgumentParser(description="Reset a user's password.")
    parser.add_argument("email", help="Email address of the account to update.")
    parser.add_argument(
        "--password",
        help="New password. Omit to generate a strong temporary one.",
    )
    parser.add_argument(
        "--deactivate",
        action="store_true",
        help="Also mark the account inactive.",
    )
    args = parser.parse_args()

    environ.Env.read_env(BASE_DIR / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_gst.settings")

    import django

    django.setup()

    from django.contrib.auth import get_user_model

    User = get_user_model()
    email = args.email.strip()
    matches = list(User.objects.filter(email__iexact=email))

    if not matches:
        print("No user found with email: {}".format(email), file=sys.stderr)
        return 1

    if len(matches) > 1:
        print(
            "Multiple users share the email {} (ids: {}). Refusing to guess.".format(
                email, ", ".join(str(u.pk) for u in matches)
            ),
            file=sys.stderr,
        )
        return 1

    user = matches[0]
    password = args.password or generate_password()

    user.set_password(password)
    fields = ["password"]
    if args.deactivate:
        user.is_active = False
        fields.append("is_active")
    user.save(update_fields=fields)

    user.refresh_from_db()
    if not user.check_password(password):
        print("Password verification failed; nothing was persisted.", file=sys.stderr)
        return 1

    print("User id     : {}".format(user.pk))
    print("Email       : {}".format(user.email))
    print("Active      : {}".format(user.is_active))
    if not args.password:
        print("Temp password: {}".format(password))
    else:
        print("Password    : updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
