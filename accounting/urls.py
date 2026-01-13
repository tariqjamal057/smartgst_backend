from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register viewsets for accounting app here, e.g.:
# router.register(r'chartofaccounts', ChartOfAccountsViewSet)
# router.register(r'vouchers', VoucherViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Add other accounting app specific URLs here
]
