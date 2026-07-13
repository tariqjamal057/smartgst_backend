from rest_framework import serializers

from tenants.models import Tenant, TenantUser


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class TenantUserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = TenantUser
        fields = ("id", "tenant", "user", "email", "name", "role", "is_active", "created_at")
        read_only_fields = ("created_at",)

    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
