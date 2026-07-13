from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for action_queue app here, e.g.:
# router.register(r'actions', ActionViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # Add other action_queue app specific URLs here
]
