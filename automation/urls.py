from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for automation app here, e.g.:
# router.register(r'reminders', ReminderViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # Add other automation app specific URLs here
]
