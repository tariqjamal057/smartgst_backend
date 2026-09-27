from django.utils import timezone

from .models import Plan, Subscription


def parse_limit(value):
    """Return int limit or None when the value means 'Unlimited'."""
    if not value:
        return None
    text = str(value).strip().lower()
    if text in ("unlimited", "unlmtd", "-", "n/a", "∞"):
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def is_expired(sub):
    return sub is not None and sub.renews_at is not None and sub.renews_at < timezone.now().date()


def get_subscription(user):
    sub = Subscription.objects.filter(user=user).select_related("plan").first()
    if sub and sub.plan_id and not is_expired(sub):
        return sub
    return None


def get_plan(user):
    sub = get_subscription(user)
    if sub:
        return sub.plan
    return Plan.objects.filter(is_active=True).order_by("sort_order").first()


def client_limit(user):
    plan = get_plan(user)
    return parse_limit(plan.clients) if plan else None


def user_limit(user):
    plan = get_plan(user)
    return parse_limit(plan.users) if plan else None
