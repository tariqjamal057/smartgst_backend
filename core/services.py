from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_email(
    subject,
    recipient_list,
    template_name=None,
    context=None,
    html_content=None,
    text_content=None,
    from_email=None,
):
    """Common base email sender.

    Accepts either a template name (rendered with context) or raw
    html/text content. Returns the number of emails sent.
    """
    if not recipient_list:
        return 0

    from_email = from_email or settings.DEFAULT_FROM_EMAIL
    html = html_content
    text = text_content

    if template_name:
        context = context or {}
        html = render_to_string(template_name, context)
        if text is None:
            text = _strip_html(html)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text or "",
        from_email=from_email,
        to=list(recipient_list),
    )
    if html:
        msg.attach_alternative(html, "text/html")
    return msg.send()


def send_invitation_email(to_email, company_name, invited_by, tenant_id):
    """Send a CA/accountant connection invitation email."""
    domain = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    subject = f"You've been invited to connect with {company_name}"
    context = {
        "company_name": company_name,
        "invited_by": invited_by,
        "tenant_id": tenant_id,
        "protocol": "https" if domain.startswith("https") else "http",
        "domain": domain.replace("http://", "").replace("https://", ""),
    }
    return send_email(
        subject=subject,
        recipient_list=[to_email],
        template_name="core/invitation_email.html",
        context=context,
    )


def send_company_deletion_email(to_email, company_name, company_id):
    """Send a company deletion confirmation email."""
    domain = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    subject = f"{company_name} has been deleted"
    context = {
        "company_name": company_name,
        "company_id": company_id,
        "protocol": "https" if domain.startswith("https") else "http",
        "domain": domain.replace("http://", "").replace("https://", ""),
    }
    return send_email(
        subject=subject,
        recipient_list=[to_email],
        template_name="core/company_deletion_email.html",
        context=context,
    )


def _strip_html(html):
    import re

    text = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
