from rest_framework.routers import DefaultRouter

from .views import VanayaViewSet

router = DefaultRouter()
router.register(r"", VanayaViewSet, basename="vanaya")

urlpatterns = router.urls
