from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for gst_engine app here, if any, e.g.:
# router.register(r'gstcalculations', GSTCalculationViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # Add other gst_engine app specific URLs here
]
