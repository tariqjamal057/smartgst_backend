from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for audit_logs app here, e.g.:
# router.register(r'auditlogs', AuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Add other audit_logs app specific URLs here
]
