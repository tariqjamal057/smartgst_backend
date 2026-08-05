from celery import shared_task

from core.services import send_company_deletion_email, send_invitation_email


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
