from django.db.models import Sum
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import (
    Account,
    BankReconciliation,
    CompanySetting,
    ContraVoucher,
    CreditNote,
    DebitNote,
    DeliveryChallan,
    Document,
    FinancialYear,
    InvoiceSetting,
    Item,
    ItemCategory,
    JournalVoucher,
    Ledger,
    Party,
    PaymentVoucher,
    PurchaseBill,
    PurchaseOrder,
    PurchaseReturn,
    ReceiptVoucher,
    SaleOrder,
    SaleReturn,
    SalesInvoice,
    Transaction,
)
from .serializers import (
    AccountSerializer,
    BankReconciliationSerializer,
    CompanySettingSerializer,
    ContraVoucherSerializer,
    CreditNoteSerializer,
    DebitNoteSerializer,
    DeliveryChallanSerializer,
    DocumentSerializer,
    FinancialYearSerializer,
    InvoiceSettingSerializer,
    ItemCategorySerializer,
    ItemSerializer,
    JournalVoucherSerializer,
    PartySerializer,
    PaymentVoucherSerializer,
    PurchaseBillSerializer,
    PurchaseOrderSerializer,
    PurchaseReturnSerializer,
    ReceiptVoucherSerializer,
    SaleOrderSerializer,
    SaleReturnSerializer,
    SalesInvoiceSerializer,
    TransactionSerializer,
)


class TenantAwareViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            return self.queryset.filter(tenant_id=tenant_id)
        return self.queryset.none()

    def perform_create(self, serializer):
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            serializer.save(tenant_id=tenant_id)


class BaseVoucherViewSet(TenantAwareViewSet):

    def perform_create(self, serializer):
        financial_year = serializer.validated_data.get("financial_year")
        if financial_year and financial_year.is_locked:
            raise ValidationError(f"Financial year {financial_year} is locked.")
        super().perform_create(serializer)

    def perform_update(self, serializer):
        if serializer.instance.is_posted:
            raise ValidationError("Cannot edit a posted voucher.")
        if serializer.instance.financial_year.is_locked:
            raise ValidationError(
                f"Financial year {serializer.instance.financial_year} is locked."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_posted:
            raise ValidationError("Cannot delete a posted voucher.")
        if instance.financial_year.is_locked:
            raise ValidationError(f"Financial year {instance.financial_year} is locked.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        voucher = self.get_object()
        if voucher.is_posted:
            return Response(
                {"detail": "This voucher has already been posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        services.post_voucher(voucher)
        return Response({"detail": "Voucher posted successfully."}, status=status.HTTP_200_OK)


class FinancialYearViewSet(TenantAwareViewSet):
    queryset = FinancialYear.objects.all()
    serializer_class = FinancialYearSerializer


class AccountViewSet(TenantAwareViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class PartyViewSet(TenantAwareViewSet):
    queryset = Party.objects.all()
    serializer_class = PartySerializer


class ItemCategoryViewSet(TenantAwareViewSet):
    queryset = ItemCategory.objects.all()
    serializer_class = ItemCategorySerializer


class ItemViewSet(TenantAwareViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer


class SalesInvoiceViewSet(BaseVoucherViewSet):
    queryset = SalesInvoice.objects.all()
    serializer_class = SalesInvoiceSerializer


class PurchaseBillViewSet(BaseVoucherViewSet):
    queryset = PurchaseBill.objects.all()
    serializer_class = PurchaseBillSerializer


class ReceiptVoucherViewSet(BaseVoucherViewSet):
    queryset = ReceiptVoucher.objects.all()
    serializer_class = ReceiptVoucherSerializer


class PaymentVoucherViewSet(BaseVoucherViewSet):
    queryset = PaymentVoucher.objects.all()
    serializer_class = PaymentVoucherSerializer


class JournalVoucherViewSet(BaseVoucherViewSet):
    queryset = JournalVoucher.objects.all()
    serializer_class = JournalVoucherSerializer


class TransactionViewSet(TenantAwareViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer


class InvoiceSettingViewSet(TenantAwareViewSet):
    queryset = InvoiceSetting.objects.all()
    serializer_class = InvoiceSettingSerializer


class SaleOrderViewSet(TenantAwareViewSet):
    queryset = SaleOrder.objects.all()
    serializer_class = SaleOrderSerializer


class PurchaseOrderViewSet(TenantAwareViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer


class DeliveryChallanViewSet(TenantAwareViewSet):
    queryset = DeliveryChallan.objects.all()
    serializer_class = DeliveryChallanSerializer

    @action(detail=True, methods=["post"])
    def mark_delivered(self, request, pk=None):
        challan = self.get_object()
        challan.status = DeliveryChallan.Status.DELIVERED
        challan.save()
        return Response({"detail": "Challan marked as delivered."})


class ContraVoucherViewSet(BaseVoucherViewSet):
    queryset = ContraVoucher.objects.all()
    serializer_class = ContraVoucherSerializer


class CreditNoteViewSet(BaseVoucherViewSet):
    queryset = CreditNote.objects.all()
    serializer_class = CreditNoteSerializer


class DebitNoteViewSet(BaseVoucherViewSet):
    queryset = DebitNote.objects.all()
    serializer_class = DebitNoteSerializer


class DocumentViewSet(TenantAwareViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer


class SaleReturnViewSet(TenantAwareViewSet):
    queryset = SaleReturn.objects.all()
    serializer_class = SaleReturnSerializer


class PurchaseReturnViewSet(TenantAwareViewSet):
    queryset = PurchaseReturn.objects.all()
    serializer_class = PurchaseReturnSerializer


class BankReconciliationViewSet(TenantAwareViewSet):
    queryset = BankReconciliation.objects.all()
    serializer_class = BankReconciliationSerializer


class CompanySettingViewSet(TenantAwareViewSet):
    queryset = CompanySetting.objects.all()
    serializer_class = CompanySettingSerializer

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


# =====================
# REPORT VIEWS
# =====================


class DashboardSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        qs = SalesInvoice.objects.all()
        pq = PurchaseBill.objects.all()
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
            pq = pq.filter(tenant_id=tenant_id)

        total_sales = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        total_purchases = pq.aggregate(t=Sum("total_amount"))["t"] or 0
        sales_count = qs.count()
        purchase_count = pq.count()
        pending_receivables = qs.filter(is_posted=False).aggregate(t=Sum("balance"))["t"] or 0
        pending_payables = pq.filter(is_posted=False).aggregate(t=Sum("balance"))["t"] or 0

        return Response(
            {
                "total_sales": total_sales,
                "total_purchases": total_purchases,
                "sales_count": sales_count,
                "purchase_count": purchase_count,
                "pending_receivables": pending_receivables,
                "pending_payables": pending_payables,
            }
        )


class TrialBalanceViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        qs = Ledger.objects.all()
        if tenant_id:
            qs = qs.filter(account__tenant_id=tenant_id)

        data = []
        accounts = (
            Account.objects.filter(tenant_id=tenant_id) if tenant_id else Account.objects.all()
        )
        for account in accounts:
            agg = qs.filter(account=account).aggregate(d=Sum("debit"), c=Sum("credit"))
            data.append(
                {
                    "account": account.name,
                    "account_type": account.account_type,
                    "debit": float(agg["d"] or 0),
                    "credit": float(agg["c"] or 0),
                }
            )
        total_d = sum(d["debit"] for d in data)
        total_c = sum(d["credit"] for d in data)
        return Response({"accounts": data, "total_debit": total_d, "total_credit": total_c})


class ProfitLossViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        qs = Ledger.objects.all()
        if tenant_id:
            qs = qs.filter(account__tenant_id=tenant_id)

        income_accounts = Account.objects.filter(account_type=Account.AccountType.REVENUE)
        expense_accounts = Account.objects.filter(account_type=Account.AccountType.EXPENSE)
        if tenant_id:
            income_accounts = income_accounts.filter(tenant_id=tenant_id)
            expense_accounts = expense_accounts.filter(tenant_id=tenant_id)

        income = []
        for a in income_accounts:
            agg = qs.filter(account=a).aggregate(c=Sum("credit"), d=Sum("debit"))
            income.append({"name": a.name, "amount": float((agg["c"] or 0) - (agg["d"] or 0))})

        expenses = []
        for a in expense_accounts:
            agg = qs.filter(account=a).aggregate(d=Sum("debit"), c=Sum("credit"))
            expenses.append({"name": a.name, "amount": float((agg["d"] or 0) - (agg["c"] or 0))})

        total_income = sum(i["amount"] for i in income)
        total_expense = sum(e["amount"] for e in expenses)
        net_profit = total_income - total_expense

        return Response(
            {
                "income": income,
                "expenses": expenses,
                "total_income": total_income,
                "total_expense": total_expense,
                "net_profit": net_profit,
            }
        )


class BalanceSheetViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        qs = Ledger.objects.all()
        if tenant_id:
            qs = qs.filter(account__tenant_id=tenant_id)

        def group_accounts(acc_type):
            accounts = Account.objects.filter(account_type=acc_type)
            if tenant_id:
                accounts = accounts.filter(tenant_id=tenant_id)
            groups = []
            for acct in accounts:
                if acct.parent:
                    group_name = acct.parent.name
                else:
                    group_name = acct.account_type.title()
                agg = qs.filter(account=acct).aggregate(d=Sum("debit"), c=Sum("credit"))
                balance = float((agg["d"] or 0) - (agg["c"] or 0))
                groups.append({"name": acct.name, "group": group_name, "amount": abs(balance)})
            return groups

        liabilities = group_accounts(Account.AccountType.LIABILITY)
        equity = group_accounts(Account.AccountType.EQUITY)
        assets = group_accounts(Account.AccountType.ASSET)

        data = {"liabilities": liabilities, "equity": equity, "assets": assets}
        return Response(data)


class CashFlowViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")

        receipts = ReceiptVoucher.objects.all()
        payments = PaymentVoucher.objects.all()
        if tenant_id:
            receipts = receipts.filter(tenant_id=tenant_id)
            payments = payments.filter(tenant_id=tenant_id)

        total_inflow = receipts.aggregate(t=Sum("amount"))["t"] or 0
        total_outflow = payments.aggregate(t=Sum("amount"))["t"] or 0

        return Response(
            {
                "total_inflow": float(total_inflow),
                "total_outflow": float(total_outflow),
                "net_cash_flow": float(total_inflow - total_outflow),
            }
        )


class GstLookupViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def retrieve(self, request, pk=None):
        gstin = pk
        return Response(
            {
                "gstin": gstin,
                "legal_name": f"Party for {gstin}",
                "address": "Auto-fetched address",
                "state": gstin[:2] if gstin and len(gstin) >= 2 else "",
                "status": "ACTIVE",
            }
        )


class LedgerViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        qs = Ledger.objects.select_related("account").all()
        if tenant_id:
            qs = qs.filter(account__tenant_id=tenant_id)

        account_id = request.query_params.get("account")
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        if account_id:
            qs = qs.filter(account_id=account_id)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        data = []
        running_balance = 0
        for entry in qs.order_by("date"):
            running_balance += float(entry.debit or 0)
            running_balance -= float(entry.credit or 0)
            data.append(
                {
                    "id": entry.uuid,
                    "date": entry.date,
                    "account": entry.account.name,
                    "debit": float(entry.debit),
                    "credit": float(entry.credit),
                    "balance": running_balance,
                }
            )
        return Response(data)
