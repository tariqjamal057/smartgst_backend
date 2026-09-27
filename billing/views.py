from django.db.models import Max
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet, ViewSet

from .models import Payment, Plan, Subscription


def plan_payload(plan):
    period_choice = dict(Plan.PERIOD_CHOICES).get(plan.period, plan.period)
    return {
        "id": plan.id,
        "name": plan.name,
        "price": str(plan.price),
        "period": plan.period,
        "period_label": period_choice,
        "custom_days": plan.custom_days,
        "currency": plan.currency,
        "clients": plan.clients,
        "users": plan.users,
        "support": plan.support,
        "color": "#4f46e5",
    }


def payment_payload(payment):
    return {
        "id": payment.id,
        "invoice_no": payment.invoice_no,
        "plan": payment.plan.name,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "method": payment.payment_method,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
    }


def make_invoice_number(user):
    year = timezone.now().year
    prefix = f"TM-{year}-"
    last = Payment.objects.filter(invoice_no__startswith=prefix).aggregate(m=Max("invoice_no"))[
        "m"
    ]
    seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def renewal_date(plan, start=None):
    base = start or timezone.now().date()
    period = (plan.period or "year").lower()
    if period == "month":
        days = 30
    elif period == "custom":
        days = plan.custom_days or 30
    else:
        days = 365
    return base + timezone.timedelta(days=days)


class PlanViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Plan.objects.filter(is_active=True).order_by("sort_order")

    def list(self, request):
        return Response([plan_payload(p) for p in self.get_queryset()])

    def retrieve(self, request, pk=None):
        plan = self.get_queryset().filter(pk=pk).first()
        if not plan:
            return Response({"detail": "Plan not found."}, status=404)
        return Response(plan_payload(plan))


class SubscriptionViewSet(ViewSet):
    permission_classes = (IsAuthenticated,)

    @action(detail=False, methods=["get"])
    def me(self, request):
        sub = Subscription.objects.filter(user=request.user).first()
        if not sub:
            default = Plan.objects.filter(is_active=True).order_by("sort_order").first()
            today = timezone.now().date()
            sub = Subscription.objects.create(
                user=request.user,
                plan=default or None,
                subscribed_at=today,
                renews_at=renewal_date(default) if default else None,
            )
        elif sub.status == "active" and sub.renews_at and sub.renews_at < timezone.now().date():
            sub.status = "expired"
            sub.save()
        return self._payload(sub)

    @action(detail=False, methods=["post"])
    def select(self, request):
        plan_id = request.data.get("plan_id")
        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({"detail": "Plan not found."}, status=400)
        sub, _ = Subscription.objects.get_or_create(
            user=request.user, defaults={"plan": plan, "status": "active"}
        )
        sub.plan = plan
        sub.status = "active"
        sub.subscribed_at = timezone.now().date()
        sub.renews_at = renewal_date(plan)
        sub.save()
        Payment.objects.create(
            user=request.user,
            plan=plan,
            invoice_no=make_invoice_number(request.user),
            amount=plan.price,
            currency=plan.currency,
            status="paid",
            payment_method="UPI",
            paid_at=timezone.now().date(),
        )
        return Response({"detail": "Plan updated.", **plan_payload(plan)})

    def _payload(self, sub):
        today = timezone.now().date()
        expired = sub.status == "active" and sub.renews_at is not None and sub.renews_at < today
        status = "expired" if expired else sub.status
        return Response(
            {
                "id": sub.id,
                "status": status,
                "subscribed_at": sub.subscribed_at.isoformat() if sub.subscribed_at else None,
                "renews_at": sub.renews_at.isoformat() if sub.renews_at else None,
                "days_left": (
                    (sub.renews_at - today).days if sub.renews_at and status != "expired" else 0
                ),
                "plan": plan_payload(sub.plan) if sub.plan else None,
            }
        )


class PaymentViewSet(ViewSet):
    permission_classes = (IsAuthenticated,)

    def list(self, request):
        qs = Payment.objects.filter(user=request.user).order_by("-created_at")
        return Response([payment_payload(p) for p in qs])

    def retrieve(self, request, pk=None):
        p = Payment.objects.filter(user=request.user, pk=pk).first()
        if not p:
            return Response({"detail": "Payment not found."}, status=404)
        return Response(payment_payload(p))
