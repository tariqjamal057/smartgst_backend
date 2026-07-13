from django.conf import settings
from django.db import models

from core.models import BaseModel


class Tenant(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    subdomain_name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    pan = models.CharField(max_length=10, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True)
    registration_type = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    subscription_expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Tenants"

    def __str__(self):
        return self.name


class TenantUser(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="tenant_users")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_users"
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ("ADMIN", "Admin"),
            ("ACCOUNTANT", "Accountant"),
            ("VIEWER", "Viewer"),
        ],
        default="VIEWER",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["tenant", "user"]]

    def __str__(self):
        return f"{self.user.email} @ {self.tenant.name}"
