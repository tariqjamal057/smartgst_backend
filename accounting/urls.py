from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountViewSet,
    BalanceSheetViewSet,
    BankReconciliationViewSet,
    CashFlowViewSet,
    CompanySettingViewSet,
    ContraVoucherViewSet,
    CreditNoteViewSet,
    DashboardSummaryViewSet,
    DebitNoteViewSet,
    DeliveryChallanViewSet,
    DocumentViewSet,
    FinancialYearViewSet,
    GstLookupViewSet,
    InvoiceSettingViewSet,
    ItemCategoryViewSet,
    ItemViewSet,
    JournalVoucherViewSet,
    LedgerViewSet,
    PartyViewSet,
    PaymentVoucherViewSet,
    ProfitLossViewSet,
    PurchaseBillViewSet,
    PurchaseOrderViewSet,
    PurchaseReturnViewSet,
    ReceiptVoucherViewSet,
    SaleOrderViewSet,
    SaleReturnViewSet,
    SalesInvoiceViewSet,
    TransactionViewSet,
    TrialBalanceViewSet,
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
router.register(r"company-settings", CompanySettingViewSet)
router.register(r"dashboard/summary", DashboardSummaryViewSet, basename="dashboard-summary")
router.register(r"reports/trial-balance", TrialBalanceViewSet, basename="trial-balance")
router.register(r"reports/profit-loss", ProfitLossViewSet, basename="profit-loss")
router.register(r"reports/balance-sheet", BalanceSheetViewSet, basename="balance-sheet")
router.register(r"reports/cash-flow", CashFlowViewSet, basename="cash-flow")
router.register(r"gst", GstLookupViewSet, basename="gst-lookup")
router.register(r"ledger", LedgerViewSet, basename="ledger")

urlpatterns = [
    path("", include(router.urls)),
]
