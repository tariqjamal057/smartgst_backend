from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from tenants.models import Company, Domain


@admin.register(Company)
class CompanyAdmin(TenantAdminMixin, admin.ModelAdmin):
    pass


@admin.register(Domain)
class DomainAdmin(TenantAdminMixin, admin.ModelAdmin):
    pass
