from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from core.models import User

from .models import (
    ApiCallLog,
    DashboardLink,
    Document,
    Firm,
    GSTClient,
    NewsArticle,
    Notification,
    Reminder,
)


class UserSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "name", "is_staff", "is_superuser")

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.email


class FirmSerializer(serializers.ModelSerializer):
    client_count = serializers.SerializerMethodField()

    class Meta:
        model = Firm
        fields = (
            "id",
            "name",
            "email",
            "plan",
            "api_key",
            "password",
            "is_active",
            "reg_date",
            "client_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"password": {"write_only": True}}

    def get_client_count(self, obj):
        return obj.clients.count()

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        if password:
            validated_data["password"] = make_password(password)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        if password:
            validated_data["password"] = make_password(password)
        return super().update(instance, validated_data)


class GSTClientSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.email", read_only=True, default="")
    firm_name = serializers.CharField(source="firm.name", read_only=True, default="")

    class Meta:
        model = GSTClient
        fields = (
            "id",
            "owner",
            "owner_name",
            "firm",
            "firm_name",
            "name",
            "gstin",
            "pan",
            "mobile",
            "email",
            "state",
            "address",
            "notes",
            "reg_date",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate_gstin(self, value):
        value = (value or "").strip().upper()
        if value and len(value) != 15:
            raise serializers.ValidationError("GSTIN must be exactly 15 characters.")
        if value and not value.isalnum():
            raise serializers.ValidationError("GSTIN must be alphanumeric.")
        return value

    def validate_pan(self, value):
        value = (value or "").strip().upper()
        if value and len(value) != 10:
            raise serializers.ValidationError("PAN must be exactly 10 characters.")
        return value

    def validate_mobile(self, value):
        value = (value or "").strip()
        if value and len(value) > 20:
            raise serializers.ValidationError("Mobile number is too long.")
        return value


class NewsArticleSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="news_type", read_only=True)
    date = serializers.CharField(source="published_date", read_only=True)
    pdf = serializers.BooleanField(source="pdf_available", read_only=True)

    class Meta:
        model = NewsArticle
        fields = (
            "id",
            "type",
            "date",
            "year",
            "month",
            "featured",
            "title",
            "summary",
            "tag",
            "pdf",
            "pdf_url",
            "created_at",
        )
        read_only_fields = ("created_at",)


class DashboardLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardLink
        fields = ("id", "kind", "label", "url", "icon", "sort_order", "is_active")


class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = ("id", "title", "date", "note", "is_done", "created_at")
        read_only_fields = ("created_at",)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "title", "message", "notification_type", "is_read", "created_at")
        read_only_fields = ("created_at",)


class DocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ("id", "name", "file", "url", "file_size", "file_type", "client", "created_at")
        read_only_fields = ("created_at",)

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return ""


class ApiCallLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = ApiCallLog
        fields = (
            "id",
            "user",
            "user_email",
            "endpoint",
            "method",
            "gstin",
            "status",
            "time_taken_ms",
            "error",
            "created_at",
        )
        read_only_fields = ("created_at",)
