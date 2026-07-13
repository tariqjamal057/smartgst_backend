from django.contrib import admin

from .models import (
    Account,
    BankReconciliation,
    CompanySetting,
    ContraVoucher,
    CreditNote,
    CreditNoteItem,
    DebitNote,
    DebitNoteItem,
    DeliveryChallan,
    DeliveryChallanItem,
    Document,
    FinancialYear,
    InvoiceSetting,
    Item,
    ItemCategory,
    JournalVoucher,
    JournalVoucherEntry,
    Ledger,
    Party,
    PaymentVoucher,
    PurchaseBill,
    PurchaseBillItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReturn,
    PurchaseReturnItem,
    ReceiptVoucher,
    SaleOrder,
    SaleOrderItem,
    SaleReturn,
    SaleReturnItem,
    SalesInvoice,
    SalesInvoiceItem,
    Transaction,
)


@admin.register(InvoiceSetting)
class InvoiceSettingAdmin(admin.ModelAdmin):
    list_display = ["voucher_type", "prefix", "next_number", "is_active"]


@admin.register(CompanySetting)
class CompanySettingAdmin(admin.ModelAdmin):
    list_display = ["company_name", "gstin", "state", "email", "is_active"]


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = ["start_date", "end_date", "is_locked"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "account_type", "parent", "is_default"]


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ["name", "party_type", "gstin", "phone"]
    list_filter = ["party_type"]


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "hsn_code"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "hsn_code", "sale_price", "purchase_price"]


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "bill_id", "party", "date", "total_amount", "is_posted"]


@admin.register(PurchaseBill)
class PurchaseBillAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "bill_id", "party", "date", "total_amount", "is_posted"]


@admin.register(ReceiptVoucher)
class ReceiptVoucherAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "party", "amount", "date", "is_posted"]


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "party", "amount", "date", "is_posted"]


@admin.register(JournalVoucher)
class JournalVoucherAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "date", "is_posted"]


@admin.register(JournalVoucherEntry)
class JournalVoucherEntryAdmin(admin.ModelAdmin):
    list_display = ["voucher", "account", "debit", "credit"]


@admin.register(ContraVoucher)
class ContraVoucherAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "from_account", "to_account", "amount", "date", "is_posted"]


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "party", "total_amount", "date", "is_posted"]


@admin.register(DebitNote)
class DebitNoteAdmin(admin.ModelAdmin):
    list_display = ["voucher_number", "party", "total_amount", "date", "is_posted"]


@admin.register(SaleOrder)
class SaleOrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "party", "date", "total_amount", "status"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "party", "date", "total_amount", "status"]


@admin.register(DeliveryChallan)
class DeliveryChallanAdmin(admin.ModelAdmin):
    list_display = ["challan_number", "party", "date", "challan_type", "status"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["receipt_no", "party", "date", "transaction_type", "received_amount"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "party", "uploaded_at"]


@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    list_display = ["return_number", "party", "date", "total_amount", "is_settled"]


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ["return_number", "party", "date", "total_amount", "is_settled"]


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ["account", "statement_date", "statement_balance", "is_reconciled"]


@admin.register(Ledger)
class LedgerAdmin(admin.ModelAdmin):
    list_display = ["account", "debit", "credit", "date"]
    list_filter = ["date"]


@admin.register(SalesInvoiceItem)
class SalesInvoiceItemAdmin(admin.ModelAdmin):
    list_display = ["invoice", "item", "quantity", "amount"]


@admin.register(PurchaseBillItem)
class PurchaseBillItemAdmin(admin.ModelAdmin):
    list_display = ["bill", "item", "quantity", "amount"]


@admin.register(SaleOrderItem)
class SaleOrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "item", "quantity", "amount"]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "item", "quantity", "amount"]


@admin.register(DeliveryChallanItem)
class DeliveryChallanItemAdmin(admin.ModelAdmin):
    list_display = ["challan", "item", "quantity", "amount"]


@admin.register(CreditNoteItem)
class CreditNoteItemAdmin(admin.ModelAdmin):
    list_display = ["credit_note", "item", "quantity", "amount"]


@admin.register(DebitNoteItem)
class DebitNoteItemAdmin(admin.ModelAdmin):
    list_display = ["debit_note", "item", "quantity", "amount"]


@admin.register(SaleReturnItem)
class SaleReturnItemAdmin(admin.ModelAdmin):
    list_display = ["sale_return", "item", "quantity", "amount"]


@admin.register(PurchaseReturnItem)
class PurchaseReturnItemAdmin(admin.ModelAdmin):
    list_display = ["purchase_return", "item", "quantity", "amount"]
