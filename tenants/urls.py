from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tenants.views import TenantUserViewSet, TenantViewSet

router = DefaultRouter()
router.register(r"tenants", TenantViewSet, basename="tenant")

tenant_router = DefaultRouter()
tenant_router.register(r"users", TenantUserViewSet, basename="tenant-user")

urlpatterns = [
    path("", include(router.urls)),
    path("tenants/<int:tenant_pk>/", include(tenant_router.urls)),
]
