from django.db import models
from django_tenants.models import DomainMixin, TenantMixin

from core.models import BaseModel


class Company(BaseModel, TenantMixin):
    name = models.CharField(max_length=100, unique=True)
    subdomain_name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)

    # Add other fields as per docs requirements
    pan = models.CharField(max_length=10, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True)
    registration_type = models.CharField(max_length=50, blank=True, null=True)

    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    def save(self, *args, **kwargs):
        self.schema_name = self.subdomain_name
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass
