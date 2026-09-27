from celery import shared_task
from django.core.mail import send_mail

from core.services import send_company_deletion_email, send_invitation_email


@shared_task
def send_otp_email_task(subject, message, to_email, from_email=None):
    """Send the account-verification OTP email asynchronously."""
    try:
        print("Subject ", subject)
        return send_mail(subject, message, from_email, [to_email])
    except Exception:
        # The OTP value itself is already logged to the terminal; email
        # failure must never block registration in the dev flow.
        return 0


@shared_task
def send_invitation_email_task(to_email, company_name, invited_by, tenant_id):
    return send_invitation_email(
        to_email=to_email,
        company_name=company_name,
        invited_by=invited_by,
        tenant_id=tenant_id,
    )


@shared_task
def send_company_deletion_email_task(to_email, company_name, company_id):
    return send_company_deletion_email(
        to_email=to_email,
        company_name=company_name,
        company_id=company_id,
    )
