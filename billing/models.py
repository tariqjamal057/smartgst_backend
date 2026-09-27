from django.conf import settings
from django.db import models

from core.models import BaseModel


class Plan(BaseModel):
    PERIOD_CHOICES = [
        ("year", "Year"),
        ("month", "Month"),
        ("custom", "Custom Days"),
    ]

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default="year")
    custom_days = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=5, default="INR")
    clients = models.CharField(max_length=50, default="0")
    users = models.CharField(max_length=50, default="1")
    support = models.CharField(max_length=50, default="Email")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.period == "custom":
            if not self.custom_days or not (1 <= self.custom_days <= 30):
                raise ValidationError({"custom_days": "Custom Days must be between 1 and 30."})
        else:
            self.custom_days = None

    def __str__(self):
        return self.name


class Subscription(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, default="active")
    subscribed_at = models.DateField(null=True, blank=True)
    renews_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} -> {self.plan.name}"


class Payment(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payments")
    invoice_no = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="INR")
    status = models.CharField(max_length=20, default="paid")
    payment_method = models.CharField(max_length=50, default="UPI")
    paid_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_no} ({self.user.email})"
