from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountViewSet,
    BackupRestoreViewSet,
    BalanceSheetViewSet,
    BankReconciliationViewSet,
    CashFlowViewSet,
    CompanySettingViewSet,
    CompanySplitViewSet,
    ConnectCAViewSet,
    ContraVoucherViewSet,
    CreditNoteViewSet,
    CustomerVendorSummaryViewSet,
    DashboardSummaryViewSet,
    DaybookViewSet,
    DebitNoteViewSet,
    DeliveryChallanSummaryViewSet,
    DeliveryChallanViewSet,
    DocumentViewSet,
    FinancialYearViewSet,
    GodownViewSet,
    GstLookupViewSet,
    GSTR1ViewSet,
    GSTR2ViewSet,
    GSTR3BViewSet,
    GSTR7ViewSet,
    HSNSACViewSet,
    InvoiceBookViewSet,
    InvoicePreferencesViewSet,
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
    PurchaseReturnSummaryViewSet,
    PurchaseReturnViewSet,
    PurchaseSummaryViewSet,
    ReceiptVoucherViewSet,
    SaleOrderSummaryViewSet,
    SaleOrderViewSet,
    SaleReturnSummaryViewSet,
    SaleReturnViewSet,
    SalesInvoiceViewSet,
    SaleSummaryViewSet,
    StockSummaryViewSet,
    TCSReportViewSet,
    TDSReportViewSet,
    TransactionViewSet,
    TrialBalanceViewSet,
)

router = DefaultRouter()
router.register(r"financial-years", FinancialYearViewSet)
router.register(r"accounts", AccountViewSet)
router.register(r"parties", PartyViewSet)
router.register(r"items", ItemViewSet)
router.register(r"item-categories", ItemCategoryViewSet)
router.register(r"godowns", GodownViewSet)
router.register(r"sales-invoices", SalesInvoiceViewSet)
router.register(r"purchase-bills", PurchaseBillViewSet)
router.register(r"receipt-vouchers", ReceiptVoucherViewSet)
router.register(r"payment-vouchers", PaymentVoucherViewSet)
router.register(r"journal-vouchers", JournalVoucherViewSet)
router.register(r"transactions", TransactionViewSet)
router.register(r"invoice-settings", InvoiceSettingViewSet)
router.register(r"invoice-preferences", InvoicePreferencesViewSet)
router.register(r"invoice-books", InvoiceBookViewSet)
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
router.register(r"connect-ca", ConnectCAViewSet, basename="connect-ca")
router.register(r"backup", BackupRestoreViewSet, basename="backup")
router.register(r"company-split", CompanySplitViewSet, basename="company-split")
router.register(r"dashboard/summary", DashboardSummaryViewSet, basename="dashboard-summary")
router.register(r"reports/trial-balance", TrialBalanceViewSet, basename="trial-balance")
router.register(r"reports/profit-loss", ProfitLossViewSet, basename="profit-loss")
router.register(r"reports/balance-sheet", BalanceSheetViewSet, basename="balance-sheet")
router.register(r"reports/cash-flow", CashFlowViewSet, basename="cash-flow")
router.register(r"reports/sale-summary", SaleSummaryViewSet, basename="sale-summary")
router.register(r"reports/purchase-summary", PurchaseSummaryViewSet, basename="purchase-summary")
router.register(
    r"reports/sale-return-summary", SaleReturnSummaryViewSet, basename="sale-return-summary"
)
router.register(
    r"reports/purchase-return-summary",
    PurchaseReturnSummaryViewSet,
    basename="purchase-return-summary",
)
router.register(
    r"reports/sale-order-summary", SaleOrderSummaryViewSet, basename="sale-order-summary"
)
router.register(
    r"reports/delivery-challan-summary",
    DeliveryChallanSummaryViewSet,
    basename="delivery-challan-summary",
)
router.register(r"reports/stock-summary", StockSummaryViewSet, basename="stock-summary")
router.register(r"reports/hsn-sac", HSNSACViewSet, basename="hsn-sac")
router.register(
    r"reports/customer-vendor-summary",
    CustomerVendorSummaryViewSet,
    basename="customer-vendor-summary",
)
router.register(r"reports/gstr1", GSTR1ViewSet, basename="gstr1")
router.register(r"reports/gstr2", GSTR2ViewSet, basename="gstr2")
router.register(r"reports/gstr3b", GSTR3BViewSet, basename="gstr3b")
router.register(r"reports/gstr7", GSTR7ViewSet, basename="gstr7")
router.register(r"reports/tds", TDSReportViewSet, basename="tds-report")
router.register(r"reports/tcs", TCSReportViewSet, basename="tcs-report")
router.register(r"reports/daybook", DaybookViewSet, basename="daybook")
router.register(r"gst", GstLookupViewSet, basename="gst-lookup")
router.register(r"ledger", LedgerViewSet, basename="ledger")

urlpatterns = [
    path("", include(router.urls)),
]
