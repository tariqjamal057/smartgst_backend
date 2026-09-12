from rest_framework import fields, serializers

from .services import RETURNS_PATH, SEARCH_PATH


class CredentialFieldsMixin:
    """Optional override of the env-configured GSP credentials.

    Only when *all four* (gstin, username, ip_usr, cust_id) are supplied does
    the base client use them; otherwise the env defaults apply (handled by
    ``VanayaClient.from_data``).
    """

    gstin = fields.CharField(required=False, allow_blank=True)
    username = fields.CharField(required=False, allow_blank=True)
    ip_usr = fields.CharField(required=False, allow_blank=True)
    cust_id = fields.CharField(required=False, allow_blank=True)


class SendOTPSerializer(CredentialFieldsMixin, serializers.Serializer):
    pass


class AuthenticateSerializer(CredentialFieldsMixin, serializers.Serializer):
    otp = fields.CharField(write_only=True, required=False, allow_blank=True, default="")


class BaseCallSerializer(CredentialFieldsMixin, serializers.Serializer):
    """Common request fields for the authenticated GET/POST handlers."""

    action = fields.CharField(required=True, allow_blank=False)

    def validate_action(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("action cannot be empty.")
        return value


class GenericGetSerializer(BaseCallSerializer):
    path = fields.ChoiceField(
        choices=[SEARCH_PATH, RETURNS_PATH],
        required=True,
    )


class GenericPostSerializer(BaseCallSerializer):
    path = fields.ChoiceField(
        choices=[RETURNS_PATH],
        required=True,
    )
    payload = fields.JSONField(required=False, default=dict, allow_null=True)
