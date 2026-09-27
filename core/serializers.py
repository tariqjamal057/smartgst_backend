from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers

from .models import NotificationPreference, User


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "uuid",
            "name",
            "first_name",
            "last_name",
            "email",
            "profile_photo",
            "gender",
            "date_of_birth",
            "address",
            "city",
            "state",
            "pincode",
            "mobile",
            "phone",
            "company",
            "gstin",
            "is_staff",
            "is_superuser",
        )
        read_only_fields = (
            "id",
            "uuid",
            "name",
            "is_staff",
            "is_superuser",
        )

    def get_name(self, obj):
        first = (obj.first_name or "").strip()
        last = (obj.last_name or "").strip()
        if first == last and first:
            return first
        return " ".join(p for p in (first, last) if p)


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    password2 = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password", "password2")
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
        }

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )  # nosec B105
        try:
            validate_password(attrs["password"])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"],
        )
        return user


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "email",
            "sms",
            "whatsapp",
            "due_reminders",
            "voucher_alerts",
            "report_alerts",
            "login_alerts",
            "payment_alerts",
        )
