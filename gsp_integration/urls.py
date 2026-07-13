from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for gsp_integration app here, e.g.:
# router.register(r'gspstatus', GSPStatusViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # Add other gsp_integration app specific URLs here
]
