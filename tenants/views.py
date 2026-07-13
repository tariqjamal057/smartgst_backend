from rest_framework import permissions, viewsets

from tenants.models import Tenant, TenantUser
from tenants.serializers import TenantSerializer, TenantUserSerializer


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAdminUser]


class TenantUserViewSet(viewsets.ModelViewSet):
    serializer_class = TenantUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TenantUser.objects.filter(tenant_id=self.kwargs.get("tenant_pk"))

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.kwargs.get("tenant_pk"))
