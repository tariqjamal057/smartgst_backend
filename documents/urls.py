from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for documents app here, e.g.:
# router.register(r'documents', DocumentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Add other documents app specific URLs here
]
