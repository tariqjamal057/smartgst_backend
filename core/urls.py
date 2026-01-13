from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for core app here, e.g.:
# router.register(r'users', UserViewSet)
# router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Add other core app specific URLs here
]
