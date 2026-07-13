from django.contrib import admin

from tenants.models import Tenant, TenantUser


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "role", "is_active")
    list_filter = ("role", "is_active")
