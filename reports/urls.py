from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for reports app here, e.g.:
# router.register(r'reports', ReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Add other reports app specific URLs here
]
