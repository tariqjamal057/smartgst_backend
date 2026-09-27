from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, PlanViewSet, SubscriptionViewSet

router = DefaultRouter()
router.register(r"plans", PlanViewSet, basename="plans")
router.register(r"subscription", SubscriptionViewSet, basename="subscription")
router.register(r"payments", PaymentViewSet, basename="payments")

urlpatterns = [
    path("", include(router.urls)),
]
