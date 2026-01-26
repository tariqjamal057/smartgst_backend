from django.urls import include, path
from rest_framework.routers import DefaultRouter

# Create a router and register our viewsets with it.
router = DefaultRouter()
# Example: router.register(r'users', UserViewSet)


# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("core/", include("core.urls")),
    path("accounting/", include("accounting.urls")),
    path("gst_engine/", include("gst_engine.urls")),
    path("gsp_integration/", include("gsp_integration.urls")),
    path("action_queue/", include("action_queue.urls")),
    path("documents/", include("documents.urls")),
    path("automation/", include("automation.urls")),
    path("reports/", include("reports.urls")),
    path("billing/", include("billing.urls")),
    path("audit_logs/", include("audit_logs.urls")),
    path("tenants/", include("tenants.urls")),
    path("", include(router.urls)),
]
