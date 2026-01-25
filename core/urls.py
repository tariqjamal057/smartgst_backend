from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView,
    LogoutView,
    RequestPasswordResetView,
    SetNewPasswordView,
    UserRegistrationView,
)

router = DefaultRouter()
# Register viewsets for core app here, e.g.:
# router.register(r'users', UserViewSet)
# router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "request-reset-password/",
        RequestPasswordResetView.as_view(),
        name="request-reset-password",
    ),
    path("reset-password-confirm/", SetNewPasswordView.as_view(), name="reset-password-confirm"),
    path("", include(router.urls)),
    # Add other core app specific URLs here
]
