from rest_framework.routers import DefaultRouter

from tenants.views import CompanyViewSet

router = DefaultRouter()
router.register(r"companies", CompanyViewSet, basename="company")
urlpatterns = router.urls
