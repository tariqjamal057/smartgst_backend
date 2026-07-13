from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountViewSet,
    BankReconciliationViewSet,
    ContraVoucherViewSet,
    CreditNoteViewSet,
    DebitNoteViewSet,
    DeliveryChallanViewSet,
    DocumentViewSet,
    FinancialYearViewSet,
    InvoiceSettingViewSet,
    ItemCategoryViewSet,
    ItemViewSet,
    JournalVoucherViewSet,
    PartyViewSet,
    PaymentVoucherViewSet,
    PurchaseBillViewSet,
    PurchaseOrderViewSet,
    PurchaseReturnViewSet,
    ReceiptVoucherViewSet,
    SaleOrderViewSet,
    SaleReturnViewSet,
    SalesInvoiceViewSet,
    TransactionViewSet,
)

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
router.register(r"invoice-settings", InvoiceSettingViewSet)
router.register(r"sale-orders", SaleOrderViewSet)
router.register(r"purchase-orders", PurchaseOrderViewSet)
router.register(r"delivery-challans", DeliveryChallanViewSet)
router.register(r"contra-vouchers", ContraVoucherViewSet)
router.register(r"credit-notes", CreditNoteViewSet)
router.register(r"debit-notes", DebitNoteViewSet)
router.register(r"documents", DocumentViewSet)
router.register(r"sale-returns", SaleReturnViewSet)
router.register(r"purchase-returns", PurchaseReturnViewSet)
router.register(r"bank-reconciliations", BankReconciliationViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
