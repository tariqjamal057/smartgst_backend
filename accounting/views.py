import json
import logging
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.tasks import send_company_deletion_email_task, send_invitation_email_task
from tenants.models import Tenant, TenantUser

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
    PurchaseBillItem,
    PurchaseOrder,
    PurchaseReturn,
    ReceiptVoucher,
    SaleOrder,
    SaleReturn,
    SalesInvoice,
    SalesInvoiceItem,
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

User = get_user_model()
logger = logging.getLogger(__name__)


class TenantAwareViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if not tenant_id:
            return self.queryset.none()
        return self.queryset.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            serializer.save(tenant_id=tenant_id)


class BackupRestoreViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _get_tenant_id(self):
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if not tenant_id:
            raise ValidationError("Tenant header missing.")
        return tenant_id

    @action(detail=False, methods=["get"])
    def export(self, request):
        tenant_id = self._get_tenant_id()
        from .backup_service import export_tenant_json

        payload = export_tenant_json(tenant_id)
        company = CompanySetting.objects.filter(id=tenant_id).first()
        company_name = company.company_name if company else "company"
        filename = f"backup_{company_name}_{date.today().isoformat()}.json"
        response = HttpResponse(payload, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def restore(self, request):
        tenant_id = self._get_tenant_id()
        from .backup_service import restore_tenant_json

        file = request.FILES.get("file")
        if not file:
            raise ValidationError("No backup file uploaded.")
        try:
            payload = json.loads(file.read().decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValidationError("Invalid JSON backup file.")
        tenant = Tenant.objects.get(id=tenant_id)
        count = restore_tenant_json(tenant, payload)
        return Response({"detail": f"Restored {count} records.", "restored": count})


class CompanySplitViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request):
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if not tenant_id:
            raise ValidationError("Tenant header missing.")
        split_date = request.data.get("split_date")
        if not split_date:
            raise ValidationError("Split date is required.")
        try:
            split_date = date.fromisoformat(str(split_date))
        except ValueError:
            raise ValidationError("Invalid split date.")
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValidationError("Tenant not found.")
        from .split_service import split_company

        result = split_company(tenant, request.user, split_date)
        return Response(result, status=status.HTTP_201_CREATED)


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
        tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            return CompanySetting.objects.filter(is_active=True, tenant_id=tenant_id)
        return CompanySetting.objects.filter(is_active=True, created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = serializer.save(created_by=request.user)
        tenant = Tenant.objects.create(
            name=f"{company.company_name} ({company.company_id})",
            subdomain_name=company.company_id,
            gstin=company.gstin or "",
        )
        company.tenant = tenant
        company.save(update_fields=["tenant"])
        TenantUser.objects.create(tenant=tenant, user=request.user, role="ADMIN")
        return Response(self.get_serializer(company).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        company = self.get_object()
        tenant = company.tenant
        if tenant is None:
            company.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        is_admin = TenantUser.objects.filter(
            tenant=tenant, user=request.user, role="ADMIN", is_active=True
        ).exists()
        if not is_admin:
            raise PermissionDenied("Only an admin can delete the company.")

        company_name = company.company_name
        company_id = company.company_id
        recipient = request.user.email

        from .backup_service import _delete_tenant_data

        Ledger.objects.filter(account__tenant_id=tenant.id).delete()
        _delete_tenant_data(tenant.id)
        tenant.delete()

        try:
            send_company_deletion_email_task.delay(recipient, company_name, company_id)
        except Exception:
            logger.exception("Failed to queue company deletion email.")

        return Response(status=status.HTTP_204_NO_CONTENT)


class ConnectCAViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if not tenant_id:
            return Response(
                {"detail": "No tenant selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"is_active": True},
        )
        if created:
            user.set_unusable_password()
            user.save()

        obj, obj_created = TenantUser.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": "ACCOUNTANT", "is_active": True},
        )
        if not obj_created and obj.role != "ACCOUNTANT":
            obj.role = "ACCOUNTANT"
            obj.is_active = True
            obj.save()

        if created or obj_created:
            try:
                send_invitation_email_task.delay(
                    to_email=user.email,
                    company_name=tenant.name,
                    invited_by=request.user.email,
                    tenant_id=tenant.id,
                )
            except Exception as exc:
                logger.exception("Failed to queue invitation email to %s: %s", user.email, exc)

        return Response(
            {
                "id": obj.id,
                "email": user.email,
                "role": obj.role,
                "tenant": tenant.id,
                "created": created or obj_created,
            },
            status=status.HTTP_201_CREATED if (created or obj_created) else status.HTTP_200_OK,
        )

    def list(self, request):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if not tenant_id:
            return Response([])
        rows = TenantUser.objects.filter(tenant_id=tenant_id, is_active=True).select_related(
            "user"
        )
        return Response(
            [
                {
                    "id": row.id,
                    "email": row.user.email,
                    "name": f"{row.user.first_name} {row.user.last_name}".strip(),
                    "role": row.role,
                }
                for row in rows
            ]
        )

    def destroy(self, request, pk=None):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if not tenant_id:
            return Response(
                {"detail": "No tenant selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            row = TenantUser.objects.get(pk=pk, tenant_id=tenant_id)
        except TenantUser.DoesNotExist:
            return Response(
                {"detail": "Connection not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if (
            row.role == "ADMIN"
            and TenantUser.objects.filter(
                tenant_id=tenant_id, role="ADMIN", is_active=True
            ).count()
            <= 1
        ):
            return Response(
                {"detail": "Cannot remove the last admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================
# REPORT VIEWS
# =====================


class DashboardSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "total_sales": 0,
                    "total_purchases": 0,
                    "sales_count": 0,
                    "purchase_count": 0,
                    "pending_receivables": 0,
                    "pending_payables": 0,
                }
            )
        qs = SalesInvoice.objects.all()
        pq = PurchaseBill.objects.all()
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
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"accounts": [], "total_debit": 0, "total_credit": 0})
        qs = Ledger.objects.all()
        qs = qs.filter(account__tenant_id=tenant_id)

        data = []
        accounts = Account.objects.filter(tenant_id=tenant_id)
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
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "income": [],
                    "expenses": [],
                    "total_income": 0,
                    "total_expense": 0,
                    "net_profit": 0,
                }
            )
        qs = Ledger.objects.all()
        qs = qs.filter(account__tenant_id=tenant_id)

        income_accounts = Account.objects.filter(account_type=Account.AccountType.REVENUE)
        expense_accounts = Account.objects.filter(account_type=Account.AccountType.EXPENSE)
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
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"liabilities": [], "equity": [], "assets": []})
        qs = Ledger.objects.all()
        qs = qs.filter(account__tenant_id=tenant_id)

        def group_accounts(acc_type):
            accounts = Account.objects.filter(account_type=acc_type)
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
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "total_inflow": 0,
                    "total_outflow": 0,
                    "net_cash_flow": 0,
                }
            )

        receipts = ReceiptVoucher.objects.all()
        payments = PaymentVoucher.objects.all()
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
        # Mock data — replace with real GST API integration later
        mock_data = {
            "success": True,
            "company_name": "TAXMATE TECHNOLOGY PRIVATE LIMITED",
            "gstin": gstin,
            "address": "No. 45, Gandhi Street, Anna Nagar",
            "branch_address": "Plot No. 12, SIPCOT Industrial Park",
            "state": "Tamil Nadu",
            "country": "India",
            "email": "info@taxmate.in",
            "website": "www.taxmate.in",
            "contact_person": "Rajesh Kumar",
            "contact_no": "9876543210",
            "status": "ACTIVE",
        }
        return Response(mock_data)


class LedgerViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response([])
        qs = Ledger.objects.select_related("account").all()
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


# =====================
# MISSING REPORT VIEWS
# =====================


def _date_filter(qs, request, date_field="date"):
    from_date = request.query_params.get("from_date")
    to_date = request.query_params.get("to_date")
    if from_date:
        qs = qs.filter(**{f"{date_field}__gte": from_date})
    if to_date:
        qs = qs.filter(**{f"{date_field}__lte": to_date})
    return qs


def _get_tenant_or_empty(request):
    tenant_id = request.META.get("HTTP_X_TENANT_ID")
    if not tenant_id:
        return None
    return tenant_id


class SaleSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"sales": [], "total": 0, "count": 0})
        qs = SalesInvoice.objects.all()
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for inv in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(inv.uuid),
                    "date": inv.date,
                    "party_name": inv.party.name if inv.party else "",
                    "voucher_number": inv.voucher_number,
                    "bill_id": inv.bill_id or "",
                    "total_amount": float(inv.total_amount),
                    "total_taxable_amount": float(inv.total_taxable_amount),
                    "total_cgst": float(inv.total_cgst),
                    "total_sgst": float(inv.total_sgst),
                    "total_igst": float(inv.total_igst),
                    "paid": float(inv.paid),
                    "balance": float(inv.balance),
                    "is_posted": inv.is_posted,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response({"sales": data, "total": float(total), "count": len(data)})


class PurchaseSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"purchases": [], "total": 0, "count": 0})
        qs = PurchaseBill.objects.all()
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for bill in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(bill.uuid),
                    "date": bill.date,
                    "party_name": bill.party.name if bill.party else "",
                    "voucher_number": bill.voucher_number,
                    "bill_id": bill.bill_id or "",
                    "total_amount": float(bill.total_amount),
                    "total_taxable_amount": float(bill.total_taxable_amount),
                    "total_cgst": float(bill.total_cgst),
                    "total_sgst": float(bill.total_sgst),
                    "total_igst": float(bill.total_igst),
                    "paid": float(bill.paid),
                    "balance": float(bill.balance),
                    "is_posted": bill.is_posted,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response({"purchases": data, "total": float(total), "count": len(data)})


class SaleReturnSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"returns": [], "total": 0, "count": 0})
        qs = SaleReturn.objects.all()
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for ret in qs.select_related("party", "invoice").order_by("date"):
            data.append(
                {
                    "id": str(ret.uuid),
                    "date": ret.date,
                    "return_number": ret.return_number,
                    "party_name": ret.party.name if ret.party else "",
                    "invoice_number": ret.invoice.bill_id if ret.invoice else "",
                    "total_amount": float(ret.total_amount),
                    "reason": ret.reason,
                    "is_settled": ret.is_settled,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response({"returns": data, "total": float(total), "count": len(data)})


class PurchaseReturnSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"returns": [], "total": 0, "count": 0})
        qs = PurchaseReturn.objects.all()
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for ret in qs.select_related("party", "bill").order_by("date"):
            data.append(
                {
                    "id": str(ret.uuid),
                    "date": ret.date,
                    "return_number": ret.return_number,
                    "party_name": ret.party.name if ret.party else "",
                    "bill_number": ret.bill.bill_id if ret.bill else "",
                    "total_amount": float(ret.total_amount),
                    "reason": ret.reason,
                    "is_settled": ret.is_settled,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response({"returns": data, "total": float(total), "count": len(data)})


class SaleOrderSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"orders": [], "total": 0, "count": 0})
        qs = SaleOrder.objects.all()
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for order in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(order.uuid),
                    "date": order.date,
                    "order_number": order.order_number,
                    "party_name": order.party.name if order.party else "",
                    "total_amount": float(order.total_amount),
                    "status": order.status,
                    "is_converted": order.is_converted,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response({"orders": data, "total": float(total), "count": len(data)})


class DeliveryChallanSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"challans": [], "total": 0, "count": 0})
        qs = DeliveryChallan.objects.all()
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for dc in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(dc.uuid),
                    "date": dc.date,
                    "challan_number": dc.challan_number,
                    "challan_type": dc.challan_type,
                    "party_name": dc.party.name if dc.party else "",
                    "total_amount": float(dc.total_amount),
                    "status": dc.status,
                    "is_invoiced": dc.is_invoiced,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response({"challans": data, "total": float(total), "count": len(data)})


class StockSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"items": [], "count": 0})
        items = Item.objects.all()
        items = items.filter(tenant_id=tenant_id)

        data = []
        for item in items.select_related("category"):
            sale_qty = 0
            purchase_qty = 0
            if tenant_id:
                sale_qty = (
                    SalesInvoiceItem.objects.filter(
                        invoice__tenant_id=tenant_id, item=item
                    ).aggregate(q=Sum("quantity"))["q"]
                    or 0
                )
                purchase_qty = (
                    PurchaseBillItem.objects.filter(
                        bill__tenant_id=tenant_id, item=item
                    ).aggregate(q=Sum("quantity"))["q"]
                    or 0
                )
            data.append(
                {
                    "id": str(item.uuid),
                    "name": item.name,
                    "hsn_code": item.hsn_code or "",
                    "category": item.category.name if item.category else "",
                    "opening_quantity": float(item.opening_quantity or 0),
                    "sale_quantity": float(sale_qty),
                    "purchase_quantity": float(purchase_qty),
                    "closing_quantity": float(
                        (item.opening_quantity or 0) + purchase_qty - sale_qty
                    ),
                    "sale_price": float(item.sale_price or 0),
                    "purchase_price": float(item.purchase_price or 0),
                    "mrp": float(item.mrp or 0),
                }
            )
        return Response({"items": data, "count": len(data)})


class HSNSACViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"hsn_summary": [], "count": 0})

        sale_items = SalesInvoiceItem.objects.all()
        purchase_items = PurchaseBillItem.objects.all()
        sale_items = sale_items.filter(invoice__tenant_id=tenant_id)
        purchase_items = purchase_items.filter(bill__tenant_id=tenant_id)
        sale_items = _date_filter(sale_items, request, date_field="invoice__date")
        purchase_items = _date_filter(purchase_items, request, date_field="bill__date")

        hsn_map = {}
        for si in sale_items.select_related("item"):
            hsn = si.item.hsn_code or "UNKNOWN"
            if hsn not in hsn_map:
                hsn_map[hsn] = {
                    "hsn_code": hsn,
                    "item_name": si.item.name,
                    "sale_quantity": 0,
                    "sale_taxable_value": 0,
                    "sale_cgst": 0,
                    "sale_sgst": 0,
                    "sale_igst": 0,
                    "purchase_quantity": 0,
                    "purchase_taxable_value": 0,
                    "purchase_cgst": 0,
                    "purchase_sgst": 0,
                    "purchase_igst": 0,
                }
            hsn_map[hsn]["sale_quantity"] += float(si.quantity)
            hsn_map[hsn]["sale_taxable_value"] += float(si.taxable_value)
            hsn_map[hsn]["sale_cgst"] += float(si.cgst)
            hsn_map[hsn]["sale_sgst"] += float(si.sgst)
            hsn_map[hsn]["sale_igst"] += float(si.igst)

        for pi in purchase_items.select_related("item"):
            hsn = pi.item.hsn_code or "UNKNOWN"
            if hsn not in hsn_map:
                hsn_map[hsn] = {
                    "hsn_code": hsn,
                    "item_name": pi.item.name,
                    "sale_quantity": 0,
                    "sale_taxable_value": 0,
                    "sale_cgst": 0,
                    "sale_sgst": 0,
                    "sale_igst": 0,
                    "purchase_quantity": 0,
                    "purchase_taxable_value": 0,
                    "purchase_cgst": 0,
                    "purchase_sgst": 0,
                    "purchase_igst": 0,
                }
            hsn_map[hsn]["purchase_quantity"] += float(pi.quantity)
            hsn_map[hsn]["purchase_taxable_value"] += float(pi.taxable_value)
            hsn_map[hsn]["purchase_cgst"] += float(pi.cgst)
            hsn_map[hsn]["purchase_sgst"] += float(pi.sgst)
            hsn_map[hsn]["purchase_igst"] += float(pi.igst)

        return Response({"hsn_summary": list(hsn_map.values()), "count": len(hsn_map)})


class CustomerVendorSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"parties": [], "count": 0})
        parties = Party.objects.all()
        parties = parties.filter(tenant_id=tenant_id)

        party_type = request.query_params.get("party_type")
        if party_type:
            parties = parties.filter(party_type=party_type)

        data = []
        for party in parties:
            sales_total = 0
            purchases_total = 0
            sales_balance = 0
            purchases_balance = 0
            if tenant_id:
                sales_total = (
                    SalesInvoice.objects.filter(party=party, tenant_id=tenant_id).aggregate(
                        t=Sum("total_amount")
                    )["t"]
                    or 0
                )
                purchases_total = (
                    PurchaseBill.objects.filter(party=party, tenant_id=tenant_id).aggregate(
                        t=Sum("total_amount")
                    )["t"]
                    or 0
                )
                sales_balance = (
                    SalesInvoice.objects.filter(party=party, tenant_id=tenant_id).aggregate(
                        t=Sum("balance")
                    )["t"]
                    or 0
                )
                purchases_balance = (
                    PurchaseBill.objects.filter(party=party, tenant_id=tenant_id).aggregate(
                        t=Sum("balance")
                    )["t"]
                    or 0
                )

            data.append(
                {
                    "id": str(party.uuid),
                    "name": party.name,
                    "party_type": party.party_type,
                    "gstin": party.gstin or "",
                    "phone": party.phone or "",
                    "email": party.email or "",
                    "total_sales": float(sales_total),
                    "total_purchases": float(purchases_total),
                    "sales_balance": float(sales_balance),
                    "purchases_balance": float(purchases_balance),
                    "net_balance": float(sales_balance - purchases_balance),
                }
            )
        return Response({"parties": data, "count": len(data)})


class GSTR1ViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "b2b": [],
                    "b2c": [],
                    "summary": {
                        "total_taxable_value": 0,
                        "total_igst": 0,
                        "total_cgst": 0,
                        "total_sgst": 0,
                        "total_cess": 0,
                    },
                }
            )
        qs = SalesInvoice.objects.filter(is_posted=True)
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        b2b = []
        for inv in qs.select_related("party").exclude(party__gstin=""):
            b2b.append(
                {
                    "gstin": inv.party.gstin if inv.party else "",
                    "party_name": inv.party.name if inv.party else "",
                    "invoice_number": inv.bill_id or inv.voucher_number,
                    "invoice_date": inv.date,
                    "invoice_value": float(inv.total_amount),
                    "taxable_value": float(inv.total_taxable_amount),
                    "place_of_supply": inv.state_of_supply or "",
                    "supply_type": inv.supply_type,
                    "rate": float(inv.items.first().gst_rate if inv.items.exists() else 0),
                    "igst": float(inv.total_igst),
                    "cgst": float(inv.total_cgst),
                    "sgst": float(inv.total_sgst),
                    "cess": float(inv.total_cess),
                }
            )
        b2c = []
        for inv in qs.filter(Q(party__isnull=True) | Q(party__gstin="")):
            b2c.append(
                {
                    "invoice_number": inv.bill_id or inv.voucher_number,
                    "invoice_date": inv.date,
                    "invoice_value": float(inv.total_amount),
                    "taxable_value": float(inv.total_taxable_amount),
                    "place_of_supply": inv.state_of_supply or "",
                    "rate": float(inv.items.first().gst_rate if inv.items.exists() else 0),
                    "igst": float(inv.total_igst),
                    "cgst": float(inv.total_cgst),
                    "sgst": float(inv.total_sgst),
                }
            )
        summary = {
            "total_taxable_value": float(qs.aggregate(t=Sum("total_taxable_amount"))["t"] or 0),
            "total_igst": float(qs.aggregate(t=Sum("total_igst"))["t"] or 0),
            "total_cgst": float(qs.aggregate(t=Sum("total_cgst"))["t"] or 0),
            "total_sgst": float(qs.aggregate(t=Sum("total_sgst"))["t"] or 0),
            "total_cess": float(qs.aggregate(t=Sum("total_cess"))["t"] or 0),
        }
        return Response({"b2b": b2b, "b2c": b2c, "summary": summary})


class GSTR2ViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "b2b": [],
                    "summary": {
                        "total_taxable_value": 0,
                        "total_igst": 0,
                        "total_cgst": 0,
                        "total_sgst": 0,
                        "total_cess": 0,
                    },
                }
            )
        qs = PurchaseBill.objects.filter(is_posted=True)
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        b2b = []
        for bill in qs.select_related("party").exclude(party__gstin=""):
            b2b.append(
                {
                    "gstin": bill.party.gstin if bill.party else "",
                    "party_name": bill.party.name if bill.party else "",
                    "bill_number": bill.bill_id or bill.voucher_number,
                    "bill_date": bill.date,
                    "bill_value": float(bill.total_amount),
                    "taxable_value": float(bill.total_taxable_amount),
                    "place_of_supply": bill.state_of_supply or "",
                    "supply_type": bill.supply_type,
                    "rate": float(bill.items.first().gst_rate if bill.items.exists() else 0),
                    "igst": float(bill.total_igst),
                    "cgst": float(bill.total_cgst),
                    "sgst": float(bill.total_sgst),
                    "cess": float(bill.total_cess),
                }
            )
        summary = {
            "total_taxable_value": float(qs.aggregate(t=Sum("total_taxable_amount"))["t"] or 0),
            "total_igst": float(qs.aggregate(t=Sum("total_igst"))["t"] or 0),
            "total_cgst": float(qs.aggregate(t=Sum("total_cgst"))["t"] or 0),
            "total_sgst": float(qs.aggregate(t=Sum("total_sgst"))["t"] or 0),
            "total_cess": float(qs.aggregate(t=Sum("total_cess"))["t"] or 0),
        }
        return Response({"b2b": b2b, "summary": summary})


class GSTR3BViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "outward_supplies": {"taxable_value": 0, "igst": 0, "cgst": 0, "sgst": 0},
                    "inward_supplies": {"taxable_value": 0, "igst": 0, "cgst": 0, "sgst": 0},
                    "net_liability": {"igst": 0, "cgst": 0, "sgst": 0},
                }
            )
        sales = SalesInvoice.objects.filter(is_posted=True)
        purchases = PurchaseBill.objects.filter(is_posted=True)
        sales = sales.filter(tenant_id=tenant_id)
        purchases = purchases.filter(tenant_id=tenant_id)
        sales = _date_filter(sales, request)
        purchases = _date_filter(purchases, request)

        outward_taxable = float(sales.aggregate(t=Sum("total_taxable_amount"))["t"] or 0)
        outward_igst = float(sales.aggregate(t=Sum("total_igst"))["t"] or 0)
        outward_cgst = float(sales.aggregate(t=Sum("total_cgst"))["t"] or 0)
        outward_sgst = float(sales.aggregate(t=Sum("total_sgst"))["t"] or 0)

        inward_taxable = float(purchases.aggregate(t=Sum("total_taxable_amount"))["t"] or 0)
        inward_igst = float(purchases.aggregate(t=Sum("total_igst"))["t"] or 0)
        inward_cgst = float(purchases.aggregate(t=Sum("total_cgst"))["t"] or 0)
        inward_sgst = float(purchases.aggregate(t=Sum("total_sgst"))["t"] or 0)

        return Response(
            {
                "outward_supplies": {
                    "taxable_value": outward_taxable,
                    "igst": outward_igst,
                    "cgst": outward_cgst,
                    "sgst": outward_sgst,
                },
                "inward_supplies": {
                    "taxable_value": inward_taxable,
                    "igst": inward_igst,
                    "cgst": inward_cgst,
                    "sgst": inward_sgst,
                },
                "net_liability": {
                    "igst": outward_igst - inward_igst,
                    "cgst": outward_cgst - inward_cgst,
                    "sgst": outward_sgst - inward_sgst,
                },
            }
        )


class GSTR7ViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"transactions": [], "count": 0})
        qs = Transaction.objects.filter(
            transaction_type__in=[
                Transaction.TransactionTypeChoices.SALE,
                Transaction.TransactionTypeChoices.PURCHASE,
            ]
        )
        qs = qs.filter(tenant_id=tenant_id)
        qs = _date_filter(qs, request)

        data = []
        for txn in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(txn.uuid),
                    "date": txn.date,
                    "party_name": txn.party.name if txn.party else "",
                    "party_gstin": txn.party.gstin if txn.party else "",
                    "voucher_type": txn.voucher_type,
                    "receipt_no": txn.receipt_no,
                    "paid_amount": float(txn.paid_amount),
                    "received_amount": float(txn.received_amount),
                }
            )
        return Response({"transactions": data, "count": len(data)})


class TDSReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"entries": [], "total_tds": 0, "count": 0})
        payments = PaymentVoucher.objects.all()
        payments = payments.filter(tenant_id=tenant_id)
        payments = _date_filter(payments, request)

        data = []
        for pmt in payments.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(pmt.uuid),
                    "date": pmt.date,
                    "party_name": pmt.party.name if pmt.party else "",
                    "party_gstin": pmt.party.gstin if pmt.party else "",
                    "voucher_number": pmt.voucher_number,
                    "amount": float(pmt.amount),
                    "section": "194C",
                    "tds_rate": 1.0,
                    "tds_amount": float(pmt.amount) * 0.01,
                }
            )
        total_tds = sum(d["tds_amount"] for d in data)
        return Response({"entries": data, "total_tds": total_tds, "count": len(data)})


class TCSReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"entries": [], "total_tcs": 0, "count": 0})
        receipts = ReceiptVoucher.objects.all()
        receipts = receipts.filter(tenant_id=tenant_id)
        receipts = _date_filter(receipts, request)

        data = []
        for rcpt in receipts.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(rcpt.uuid),
                    "date": rcpt.date,
                    "party_name": rcpt.party.name if rcpt.party else "",
                    "party_gstin": rcpt.party.gstin if rcpt.party else "",
                    "voucher_number": rcpt.voucher_number,
                    "amount": float(rcpt.amount),
                    "section": "206C",
                    "tcs_rate": 0.1,
                    "tcs_amount": float(rcpt.amount) * 0.001,
                }
            )
        total_tcs = sum(d["tcs_amount"] for d in data)
        return Response({"entries": data, "total_tcs": total_tcs, "count": len(data)})


class DaybookViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {"entries": [], "total_received": 0, "total_paid": 0, "net": 0, "count": 0}
            )
        date = request.query_params.get("date")

        transactions = Transaction.objects.all()
        transactions = transactions.filter(tenant_id=tenant_id)
        if date:
            transactions = transactions.filter(date=date)
        else:
            transactions = _date_filter(transactions, request)

        data = []
        for txn in transactions.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(txn.uuid),
                    "date": txn.date,
                    "party_name": txn.party.name if txn.party else "",
                    "voucher_type": txn.voucher_type,
                    "transaction_type": txn.transaction_type,
                    "receipt_no": txn.receipt_no,
                    "paid_amount": float(txn.paid_amount),
                    "received_amount": float(txn.received_amount),
                    "description": txn.description,
                }
            )
        total_received = sum(d["received_amount"] for d in data)
        total_paid = sum(d["paid_amount"] for d in data)
        return Response(
            {
                "entries": data,
                "total_received": total_received,
                "total_paid": total_paid,
                "net": total_received - total_paid,
                "count": len(data),
            }
        )
