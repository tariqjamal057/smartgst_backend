from django.conf import settings
from rest_framework import serializers

from tenants.models import Company, Domain


class CompanySerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        # Create the company (tenant)
        company = super().create(validated_data)

        # Create the domain using the host from settings
        subdomain = validated_data.get("subdomain_name")
        domain_str = f"{subdomain}.{settings.TENANT_DOMAIN_HOST}"

        Domain.objects.create(domain=domain_str, tenant=company, is_primary=True)

        return company

    class Meta:
        model = Company
        fields = "__all__"
        read_only_fields = ("schema_name",)
