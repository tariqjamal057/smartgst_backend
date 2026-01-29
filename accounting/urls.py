from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountViewSet,
    FinancialYearViewSet,
    ItemCategoryViewSet,
    ItemViewSet,
    JournalVoucherViewSet,
    PartyViewSet,
    PaymentVoucherViewSet,
    PurchaseBillViewSet,
    ReceiptVoucherViewSet,
    SalesInvoiceViewSet,
    TransactionViewSet,
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r"financial-years", FinancialYearViewSet)
router.register(r"accounts", AccountViewSet)
router.register(r"parties", PartyViewSet)
router.register(r"items", ItemViewSet)
router.register(r"item-categories", ItemCategoryViewSet)
router.register(r"sales-invoices", SalesInvoiceViewSet)
router.register(r"purchase-bills", PurchaseBillViewSet)
router.register(r"receipt-vouchers", ReceiptVoucherViewSet)
router.register(r"payment-vouchers", PaymentVoucherViewSet)
router.register(r"journal-vouchers", JournalVoucherViewSet)
router.register(r"transactions", TransactionViewSet)


# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("", include(router.urls)),
]
