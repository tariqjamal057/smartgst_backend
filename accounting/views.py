import json
import logging
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Max, Q, Sum
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
    Godown,
    InvoiceBook,
    InvoicePreferences,
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
    GodownSerializer,
    InvoiceBookSerializer,
    InvoicePreferencesSerializer,
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


class FinancialYearProvisionMixin:
    def _get_current_financial_year(self, tenant_id):
        today = date.today()
        start_year = today.year if today.month >= 4 else today.year - 1
        start = date(start_year, 4, 1)
        end = date(start_year + 1, 3, 31)
        fy, _ = FinancialYear.objects.get_or_create(
            tenant_id=tenant_id,
            start_date=start,
            defaults={"end_date": end, "is_locked": False},
        )
        return fy

    def perform_create(self, serializer):
        financial_year = serializer.validated_data.get("financial_year")
        if financial_year is None:
            tenant_id = self.request.META.get("HTTP_X_TENANT_ID")
            financial_year = self._get_current_financial_year(tenant_id)
            serializer.validated_data["financial_year"] = financial_year
        if financial_year and financial_year.is_locked:
            raise ValidationError(f"Financial year {financial_year} is locked.")
        try:
            super().perform_create(serializer)
        except IntegrityError:
            raise ValidationError(
                "A voucher with this number already exists for the current financial year."
            )


class BaseVoucherViewSet(FinancialYearProvisionMixin, TenantAwareViewSet):

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

    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            name = serializer.validated_data.get("name")
            raise ValidationError(f"An account named '{name}' already exists in this company.")


class PartyViewSet(TenantAwareViewSet):
    queryset = Party.objects.all()
    serializer_class = PartySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        party_type = self.request.query_params.get("type") or self.request.query_params.get(
            "party_type"
        )
        if party_type and party_type.strip().upper() in Party.PartyType.values:
            qs = qs.filter(party_type=party_type.strip().upper())
        return qs

    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            name = serializer.validated_data.get("name")
            raise ValidationError(f"A party named '{name}' already exists in this company.")


class ItemCategoryViewSet(TenantAwareViewSet):
    queryset = ItemCategory.objects.all()
    serializer_class = ItemCategorySerializer


class GodownViewSet(TenantAwareViewSet):
    queryset = Godown.objects.all()
    serializer_class = GodownSerializer


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


class InvoicePreferencesViewSet(TenantAwareViewSet):
    queryset = InvoicePreferences.objects.all()
    serializer_class = InvoicePreferencesSerializer

    def list(self, request, *args, **kwargs):
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        obj, _ = InvoicePreferences.objects.get_or_create(tenant_id=tenant_id)
        return Response(self.get_serializer(obj).data)


class InvoiceBookViewSet(TenantAwareViewSet):
    queryset = InvoiceBook.objects.all()
    serializer_class = InvoiceBookSerializer


class SaleOrderViewSet(FinancialYearProvisionMixin, TenantAwareViewSet):
    queryset = SaleOrder.objects.all()
    serializer_class = SaleOrderSerializer


class PurchaseOrderViewSet(FinancialYearProvisionMixin, TenantAwareViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer


class DeliveryChallanViewSet(FinancialYearProvisionMixin, TenantAwareViewSet):
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

    _MONTH_NAMES = [
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
        "Jan",
        "Feb",
        "Mar",
    ]
    _DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    @staticmethod
    def _fy_bounds(today):
        start_year = today.year if today.month >= 4 else today.year - 1
        return date(start_year, 4, 1), date(start_year + 1, 3, 31)

    def _empty_payload(self):
        block = {"igst": 0, "cgst": 0, "sgst": 0, "cess": 0, "total": 0}
        return {
            "total_sales": 0,
            "total_purchases": 0,
            "sales_count": 0,
            "purchase_count": 0,
            "total_receipts": 0,
            "total_payments": 0,
            "direct_expenses": 0,
            "indirect_expenses": 0,
            "net_profit": 0,
            "pending_receivables": 0,
            "pending_payables": 0,
            "cash": 0,
            "bank": 0,
            "assets": 0,
            "liabilities": 0,
            "stock_balance": 0,
            "stock_in": 0,
            "stock_out": 0,
            "gst_data": {
                "netOutput": dict(block),
                "lessInput": dict(block),
                "itcPayable": dict(block),
            },
            "ewb_status": {"generated": 0, "sales": 0},
            "einvoice_status": {"generated": 0, "sales": 0, "pending": 0},
            "trend_stats": {
                "highestSales": "—",
                "highestSalesMonth": "—",
                "lowestSales": "—",
                "lowestSalesMonth": "—",
                "avgMonthlySales": 0,
                "avgProfitMargin": 0,
            },
            "chart_data": {
                "daily_labels": self._DAY_NAMES,
                "daily_sales": [0] * 7,
                "daily_purchase": [0] * 7,
                "daily_expenses": [0] * 7,
                "daily_profit": [0] * 7,
                "monthly_labels": self._MONTH_NAMES,
                "monthly_sales": [0] * 12,
                "monthly_purchase": [0] * 12,
                "monthly_expenses": [0] * 12,
                "monthly_profit": [0] * 12,
                "quarterly_labels": ["Q1", "Q2", "Q3", "Q4"],
                "quarterly_sales": [0] * 4,
                "quarterly_purchase": [0] * 4,
                "quarterly_expenses": [0] * 4,
                "quarterly_profit": [0] * 4,
                "yearly_labels": [],
                "yearly_sales": [],
                "yearly_purchase": [],
                "yearly_expenses": [],
                "yearly_profit": [],
            },
            "pending_receipts": [],
            "pending_payments": [],
            "recent_entries": [],
        }

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(self._empty_payload())

        today = date.today()
        fy_start, fy_end = self._fy_bounds(today)
        start_year = fy_start.year

        invoices = SalesInvoice.objects.filter(tenant_id=tenant_id)
        purchases = PurchaseBill.objects.filter(tenant_id=tenant_id)
        ledgers = Ledger.objects.filter(account__tenant_id=tenant_id)

        total_sales = float(invoices.aggregate(t=Sum("total_amount"))["t"] or 0)
        total_purchases = float(purchases.aggregate(t=Sum("total_amount"))["t"] or 0)
        sales_count = invoices.count()
        purchase_count = purchases.count()
        pending_receivables = float(
            invoices.filter(is_posted=False).aggregate(t=Sum("balance"))["t"] or 0
        )
        pending_payables = float(
            purchases.filter(is_posted=False).aggregate(t=Sum("balance"))["t"] or 0
        )
        total_receipts = float(
            ReceiptVoucher.objects.filter(tenant_id=tenant_id).aggregate(t=Sum("amount"))["t"] or 0
        )
        total_payments = float(
            PaymentVoucher.objects.filter(tenant_id=tenant_id).aggregate(t=Sum("amount"))["t"] or 0
        )

        expense_accounts = Account.objects.filter(
            tenant_id=tenant_id, account_type=Account.AccountType.EXPENSE
        )
        revenue_accounts = Account.objects.filter(
            tenant_id=tenant_id, account_type=Account.AccountType.REVENUE
        )
        asset_accounts = Account.objects.filter(
            tenant_id=tenant_id, account_type=Account.AccountType.ASSET
        )

        direct_expenses = 0.0
        indirect_expenses = 0.0
        for account in expense_accounts:
            agg = ledgers.filter(account=account).aggregate(d=Sum("debit"), c=Sum("credit"))
            amount = float((agg["d"] or 0) - (agg["c"] or 0))
            name = (account.name or "").lower()
            if any(
                key in name for key in ("purchase", "direct", "material", "cogs", "raw material")
            ):
                direct_expenses += amount
            else:
                indirect_expenses += amount

        total_income = 0.0
        for account in revenue_accounts:
            agg = ledgers.filter(account=account).aggregate(c=Sum("credit"), d=Sum("debit"))
            total_income += float((agg["c"] or 0) - (agg["d"] or 0))
        net_profit = total_income - direct_expenses - indirect_expenses

        cash = 0.0
        bank = 0.0
        assets = 0.0
        for account in asset_accounts:
            agg = ledgers.filter(account=account).aggregate(d=Sum("debit"), c=Sum("credit"))
            balance = float((agg["d"] or 0) - (agg["c"] or 0))
            assets += balance
            name = (account.name or "").lower()
            if "cash" in name:
                cash += balance
            elif "bank" in name:
                bank += balance

        liabilities = 0.0
        for account in Account.objects.filter(
            tenant_id=tenant_id,
            account_type__in=[Account.AccountType.LIABILITY, Account.AccountType.EQUITY],
        ):
            agg = ledgers.filter(account=account).aggregate(c=Sum("credit"), d=Sum("debit"))
            liabilities += float((agg["c"] or 0) - (agg["d"] or 0))

        opening_stock = float(
            Item.objects.filter(tenant_id=tenant_id).aggregate(t=Sum("opening_quantity"))["t"] or 0
        )
        sold_qty = float(
            SalesInvoiceItem.objects.filter(invoice__tenant_id=tenant_id).aggregate(
                t=Sum("quantity")
            )["t"]
            or 0
        )
        bought_qty = float(
            PurchaseBillItem.objects.filter(bill__tenant_id=tenant_id).aggregate(
                t=Sum("quantity")
            )["t"]
            or 0
        )
        stock_in = opening_stock + bought_qty
        stock_out = sold_qty
        stock_balance = stock_in - stock_out

        pending_receipts = []
        for inv in invoices.filter(is_posted=False).select_related("party").order_by("-date")[:10]:
            pending_receipts.append(
                {
                    "party": inv.party.name if inv.party else "",
                    "amount": float(inv.balance or 0),
                    "due_days": (today - inv.date).days if inv.date else 0,
                }
            )
        pending_payments = []
        for bill in (
            purchases.filter(is_posted=False).select_related("party").order_by("-date")[:10]
        ):
            pending_payments.append(
                {
                    "party": bill.party.name if bill.party else "",
                    "amount": float(bill.balance or 0),
                    "due_days": (today - bill.date).days if bill.date else 0,
                }
            )

        def _gst_sums(items_qs):
            return {
                "igst": float(items_qs.aggregate(t=Sum("igst"))["t"] or 0),
                "cgst": float(items_qs.aggregate(t=Sum("cgst"))["t"] or 0),
                "sgst": float(items_qs.aggregate(t=Sum("sgst"))["t"] or 0),
                "cess": float(items_qs.aggregate(t=Sum("cess"))["t"] or 0),
            }

        def _gst_block(sums):
            return {
                "igst": sums["igst"],
                "cgst": sums["cgst"],
                "sgst": sums["sgst"],
                "cess": sums["cess"],
                "total": sums["igst"] + sums["cgst"] + sums["sgst"] + sums["cess"],
            }

        outward = _gst_sums(SalesInvoiceItem.objects.filter(invoice__tenant_id=tenant_id))
        inward = _gst_sums(PurchaseBillItem.objects.filter(bill__tenant_id=tenant_id))
        gst_data = {
            "netOutput": _gst_block(outward),
            "lessInput": _gst_block(inward),
            "itcPayable": _gst_block(
                {
                    "igst": outward["igst"] - inward["igst"],
                    "cgst": outward["cgst"] - inward["cgst"],
                    "sgst": outward["sgst"] - inward["sgst"],
                    "cess": outward["cess"] - inward["cess"],
                }
            ),
        }

        ewb_generated = invoices.exclude(eway_bill_no="").count()
        ewb_status = {"generated": ewb_generated, "sales": sales_count}
        einvoice_status = {"generated": 0, "sales": sales_count, "pending": sales_count}

        fy_invoices = invoices.filter(date__gte=fy_start, date__lte=fy_end)
        fy_purchases = purchases.filter(date__gte=fy_start, date__lte=fy_end)
        monthly_sales = []
        monthly_purchase = []
        monthly_expenses = []
        monthly_profit = []
        for month in range(1, 13):
            s = float(
                fy_invoices.filter(date__month=month).aggregate(t=Sum("total_amount"))["t"] or 0
            )
            p = float(
                fy_purchases.filter(date__month=month).aggregate(t=Sum("total_amount"))["t"] or 0
            )
            e = float(
                ledgers.filter(
                    date__gte=fy_start,
                    date__lte=fy_end,
                    date__month=month,
                    account__account_type=Account.AccountType.EXPENSE,
                ).aggregate(t=Sum("debit"))["t"]
                or 0
            )
            monthly_sales.append(round(s, 2))
            monthly_purchase.append(round(p, 2))
            monthly_expenses.append(round(e, 2))
            monthly_profit.append(round(s - p - e, 2))

        def month_name(month):
            return self._MONTH_NAMES[(month - 4) % 12]

        sales_vals = [v for v in monthly_sales if v]
        highest = max(sales_vals) if sales_vals else None
        lowest = min(sales_vals) if sales_vals else None
        trend_stats = {
            "highestSales": highest if highest is not None else "—",
            "highestSalesMonth": (
                month_name(monthly_sales.index(highest) + 1) if highest is not None else "—"
            ),
            "lowestSales": lowest if lowest is not None else "—",
            "lowestSalesMonth": (
                month_name(monthly_sales.index(lowest) + 1) if lowest is not None else "—"
            ),
            "avgMonthlySales": round(sum(monthly_sales) / 12, 2),
            "avgProfitMargin": round((net_profit / total_sales * 100), 2) if total_sales else 0,
        }

        daily_labels = []
        daily_sales = []
        daily_purchase = []
        daily_expenses = []
        daily_profit = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            s = float(invoices.filter(date=day).aggregate(t=Sum("total_amount"))["t"] or 0)
            p = float(purchases.filter(date=day).aggregate(t=Sum("total_amount"))["t"] or 0)
            e = float(
                ledgers.filter(
                    date=day, account__account_type=Account.AccountType.EXPENSE
                ).aggregate(t=Sum("debit"))["t"]
                or 0
            )
            daily_labels.append(self._DAY_NAMES[day.weekday()])
            daily_sales.append(round(s, 2))
            daily_purchase.append(round(p, 2))
            daily_expenses.append(round(e, 2))
            daily_profit.append(round(s - p - e, 2))

        def _quarterly(values):
            return [
                round(values[0] + values[1] + values[2], 2),
                round(values[3] + values[4] + values[5], 2),
                round(values[6] + values[7] + values[8], 2),
                round(values[9] + values[10] + values[11], 2),
            ]

        yearly_labels = []
        yearly_sales = []
        yearly_purchase = []
        yearly_expenses = []
        yearly_profit = []
        for year in range(start_year - 3, start_year + 1):
            start = date(year, 4, 1)
            end = date(year + 1, 3, 31)
            s = float(
                invoices.filter(date__range=[start, end]).aggregate(t=Sum("total_amount"))["t"]
                or 0
            )
            p = float(
                purchases.filter(date__range=[start, end]).aggregate(t=Sum("total_amount"))["t"]
                or 0
            )
            e = float(
                ledgers.filter(
                    date__range=[start, end], account__account_type=Account.AccountType.EXPENSE
                ).aggregate(t=Sum("debit"))["t"]
                or 0
            )
            yearly_labels.append(f"{year}-{str(year + 1)[-2:]}")
            yearly_sales.append(round(s, 2))
            yearly_purchase.append(round(p, 2))
            yearly_expenses.append(round(e, 2))
            yearly_profit.append(round(s - p - e, 2))

        chart_data = {
            "daily_labels": daily_labels,
            "daily_sales": daily_sales,
            "daily_purchase": daily_purchase,
            "daily_expenses": daily_expenses,
            "daily_profit": daily_profit,
            "monthly_labels": self._MONTH_NAMES,
            "monthly_sales": monthly_sales,
            "monthly_purchase": monthly_purchase,
            "monthly_expenses": monthly_expenses,
            "monthly_profit": monthly_profit,
            "quarterly_labels": ["Q1", "Q2", "Q3", "Q4"],
            "quarterly_sales": _quarterly(monthly_sales),
            "quarterly_purchase": _quarterly(monthly_purchase),
            "quarterly_expenses": _quarterly(monthly_expenses),
            "quarterly_profit": _quarterly(monthly_profit),
            "yearly_labels": yearly_labels,
            "yearly_sales": yearly_sales,
            "yearly_purchase": yearly_purchase,
            "yearly_expenses": yearly_expenses,
            "yearly_profit": yearly_profit,
        }

        def _party_name(party):
            return party.name if party else ""

        recent_entries = []
        for inv in invoices.select_related("party").order_by("-date")[:5]:
            recent_entries.append(
                {
                    "date": inv.date,
                    "party": _party_name(inv.party),
                    "voucher_type": "Sales",
                    "voucher_no": inv.voucher_number,
                    "amount_cr": 0.0,
                    "amount_dr": float(inv.total_amount),
                }
            )
        for bill in purchases.select_related("party").order_by("-date")[:5]:
            recent_entries.append(
                {
                    "date": bill.date,
                    "party": _party_name(bill.party),
                    "voucher_type": "Purchase",
                    "voucher_no": bill.voucher_number,
                    "amount_cr": float(bill.total_amount),
                    "amount_dr": 0.0,
                }
            )
        for rv in (
            ReceiptVoucher.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": rv.date,
                    "party": _party_name(rv.party),
                    "voucher_type": "Receipt",
                    "voucher_no": rv.voucher_number,
                    "amount_cr": float(rv.amount),
                    "amount_dr": 0.0,
                }
            )
        for pv in (
            PaymentVoucher.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": pv.date,
                    "party": _party_name(pv.party),
                    "voucher_type": "Payment",
                    "voucher_no": pv.voucher_number,
                    "amount_cr": 0.0,
                    "amount_dr": float(pv.amount),
                }
            )
        for jv in JournalVoucher.objects.filter(tenant_id=tenant_id).order_by("-date")[:5]:
            recent_entries.append(
                {
                    "date": jv.date,
                    "party": "",
                    "voucher_type": "Journal",
                    "voucher_no": jv.voucher_number,
                    "amount_cr": 0.0,
                    "amount_dr": 0.0,
                }
            )
        for cn in (
            CreditNote.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": cn.date,
                    "party": _party_name(cn.party),
                    "voucher_type": "Credit Note",
                    "voucher_no": cn.voucher_number,
                    "amount_cr": float(cn.total_amount),
                    "amount_dr": 0.0,
                }
            )
        for dn in (
            DebitNote.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": dn.date,
                    "party": _party_name(dn.party),
                    "voucher_type": "Debit Note",
                    "voucher_no": dn.voucher_number,
                    "amount_cr": 0.0,
                    "amount_dr": float(dn.total_amount),
                }
            )
        for ct in ContraVoucher.objects.filter(tenant_id=tenant_id).order_by("-date")[:5]:
            recent_entries.append(
                {
                    "date": ct.date,
                    "party": "",
                    "voucher_type": "Contra",
                    "voucher_no": ct.voucher_number,
                    "amount_cr": float(ct.amount),
                    "amount_dr": 0.0,
                }
            )
        for so in (
            SaleOrder.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": so.date,
                    "party": _party_name(so.party),
                    "voucher_type": "Sale Order",
                    "voucher_no": so.order_number,
                    "amount_cr": float(so.total_amount),
                    "amount_dr": 0.0,
                }
            )
        for po in (
            PurchaseOrder.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": po.date,
                    "party": _party_name(po.party),
                    "voucher_type": "Purchase Order",
                    "voucher_no": po.order_number,
                    "amount_cr": 0.0,
                    "amount_dr": float(po.total_amount),
                }
            )
        for dc in (
            DeliveryChallan.objects.filter(tenant_id=tenant_id)
            .select_related("party")
            .order_by("-date")[:5]
        ):
            recent_entries.append(
                {
                    "date": dc.date,
                    "party": _party_name(dc.party),
                    "voucher_type": "Delivery Challan",
                    "voucher_no": dc.challan_number,
                    "amount_cr": 0.0,
                    "amount_dr": float(dc.total_amount),
                }
            )
        recent_entries.sort(key=lambda e: e["date"] or date.min, reverse=True)
        recent_entries = recent_entries[:10]

        return Response(
            {
                "total_sales": round(total_sales, 2),
                "total_purchases": round(total_purchases, 2),
                "sales_count": sales_count,
                "purchase_count": purchase_count,
                "total_receipts": round(total_receipts, 2),
                "total_payments": round(total_payments, 2),
                "direct_expenses": round(direct_expenses, 2),
                "indirect_expenses": round(indirect_expenses, 2),
                "net_profit": round(net_profit, 2),
                "pending_receivables": round(pending_receivables, 2),
                "pending_payables": round(pending_payables, 2),
                "cash": round(cash, 2),
                "bank": round(bank, 2),
                "assets": round(assets, 2),
                "liabilities": round(liabilities, 2),
                "stock_balance": round(stock_balance, 2),
                "stock_in": round(stock_in, 2),
                "stock_out": round(stock_out, 2),
                "gst_data": gst_data,
                "ewb_status": ewb_status,
                "einvoice_status": einvoice_status,
                "trend_stats": trend_stats,
                "chart_data": chart_data,
                "pending_receipts": pending_receipts,
                "pending_payments": pending_payments,
                "recent_entries": recent_entries,
            }
        )


class TrialBalanceViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"groups": [], "total_debit": 0, "total_credit": 0})
        from_date = _parse_date(request.query_params.get("from_date"))
        to_date = _parse_date(request.query_params.get("to_date"))

        accounts = Account.objects.filter(tenant_id=tenant_id)
        groups = {}
        total_d = 0
        total_c = 0
        for account in accounts:
            qs = Ledger.objects.filter(account=account)
            period_qs = qs
            opening_d = 0
            opening_c = 0
            if from_date:
                opening_d = qs.filter(date__lt=from_date).aggregate(d=Sum("debit"))["d"] or 0
                opening_c = qs.filter(date__lt=from_date).aggregate(c=Sum("credit"))["c"] or 0
                period_qs = qs.filter(date__gte=from_date)
            if to_date:
                period_qs = period_qs.filter(date__lte=to_date)
            d = float(period_qs.aggregate(d=Sum("debit"))["d"] or 0)
            c = float(period_qs.aggregate(c=Sum("credit"))["c"] or 0)
            group_name = account.parent.name if account.parent else account.account_type.title()
            groups.setdefault(group_name, []).append(
                {
                    "name": account.name,
                    "debit": d,
                    "credit": c,
                    "opening_debit": float(opening_d),
                    "opening_credit": float(opening_c),
                }
            )
            total_d += d
            total_c += c

        data = [{"group": g, "children": children} for g, children in groups.items()]
        return Response({"groups": data, "total_debit": total_d, "total_credit": total_c})


class ProfitLossViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    _DIRECT_EXPENSE_KEYWORDS = (
        "purchase",
        "direct",
        "raw material",
        "material",
        "carriage",
        "freight",
        "manufactur",
        "factory",
        "wages",
        "cost of",
        "stock",
    )
    _SALES_KEYWORDS = ("sales", "revenue")

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "trading": {},
                    "income_statement": {},
                    "gross_profit": 0,
                    "net_profit": 0,
                }
            )
        from_date = _parse_date(request.query_params.get("from_date"))
        to_date = _parse_date(request.query_params.get("to_date"))
        qs = Ledger.objects.filter(account__tenant_id=tenant_id)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        def bucket(label, amounts):
            return {
                "total": round(sum(a["amount"] for a in amounts), 2),
                "items": [{"name": a["name"], "amount": round(a["amount"], 2)} for a in amounts],
            }

        sales = []
        indirect_income = []
        purchases = []
        direct_expenses = []
        indirect_expenses = []

        revenue = Account.objects.filter(
            tenant_id=tenant_id, account_type=Account.AccountType.REVENUE
        )
        for a in revenue:
            agg = qs.filter(account=a).aggregate(c=Sum("credit"), d=Sum("debit"))
            amount = float((agg["c"] or 0) - (agg["d"] or 0))
            text = f"{a.name} {a.parent.name if a.parent else ''}".lower()
            if any(k in text for k in self._SALES_KEYWORDS):
                sales.append({"name": a.name, "amount": amount})
            else:
                indirect_income.append({"name": a.name, "amount": amount})

        expense = Account.objects.filter(
            tenant_id=tenant_id, account_type=Account.AccountType.EXPENSE
        )
        for a in expense:
            agg = qs.filter(account=a).aggregate(d=Sum("debit"), c=Sum("credit"))
            amount = float((agg["d"] or 0) - (agg["c"] or 0))
            text = f"{a.name} {a.parent.name if a.parent else ''}".lower()
            if "purchase" in text:
                purchases.append({"name": a.name, "amount": amount})
            elif any(k in text for k in self._DIRECT_EXPENSE_KEYWORDS):
                direct_expenses.append({"name": a.name, "amount": amount})
            else:
                indirect_expenses.append({"name": a.name, "amount": amount})

        # Stock valuation (opening / closing)
        stock_items = []
        opening_total = 0
        closing_total = 0
        items = Item.objects.filter(tenant_id=tenant_id)
        for item in items:
            rate = float(item.purchase_price or item.at_price or 0)
            purchase_qty = (
                PurchaseBillItem.objects.filter(bill__tenant_id=tenant_id, item=item).aggregate(
                    q=Sum("quantity")
                )["q"]
                or 0
            )
            sale_qty = (
                SalesInvoiceItem.objects.filter(invoice__tenant_id=tenant_id, item=item).aggregate(
                    q=Sum("quantity")
                )["q"]
                or 0
            )
            opening_qty = float(item.opening_quantity or 0)
            closing_qty = opening_qty + float(purchase_qty) - float(sale_qty)
            opening_total += opening_qty * rate
            closing_total += closing_qty * rate
            stock_items.append({"name": item.name, "amount": round(closing_qty * rate, 2)})

        sales_total = sum(s["amount"] for s in sales)
        purchases_total = sum(p["amount"] for p in purchases)
        direct_total = sum(d["amount"] for d in direct_expenses)
        opening_total = round(opening_total, 2)
        closing_total = round(closing_total, 2)
        gross_profit = sales_total + closing_total - opening_total - purchases_total - direct_total
        indirect_income_total = sum(i["amount"] for i in indirect_income)
        indirect_expense_total = sum(i["amount"] for i in indirect_expenses)
        net_profit = gross_profit + indirect_income_total - indirect_expense_total

        return Response(
            {
                "trading": {
                    "sales": bucket("sales", sales),
                    "opening_stock": {
                        "total": opening_total,
                        "items": [{"name": "Opening Stock", "amount": opening_total}],
                    },
                    "purchases": bucket("purchases", purchases),
                    "direct_expenses": bucket("direct_expenses", direct_expenses),
                    "closing_stock": {"total": closing_total, "items": stock_items},
                },
                "income_statement": {
                    "indirect_income": bucket("indirect_income", indirect_income),
                    "indirect_expenses": bucket("indirect_expenses", indirect_expenses),
                },
                "gross_profit": round(gross_profit, 2),
                "net_profit": round(net_profit, 2),
            }
        )


class BalanceSheetViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"liabilities": [], "assets": [], "total": 0})
        qs = Ledger.objects.all()
        qs = qs.filter(account__tenant_id=tenant_id)
        from_date = _parse_date(request.query_params.get("from_date"))
        to_date = _parse_date(request.query_params.get("to_date"))
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        def group_accounts(acc_type):
            accounts = Account.objects.filter(account_type=acc_type, tenant_id=tenant_id)
            groups = {}
            for acct in accounts:
                agg = qs.filter(account=acct).aggregate(d=Sum("debit"), c=Sum("credit"))
                balance = float((agg["d"] or 0) - (agg["c"] or 0))
                if acc_type == Account.AccountType.ASSET:
                    balance = abs(balance)
                group_name = acct.parent.name if acct.parent else acct.account_type.title()
                group = groups.setdefault(
                    group_name, {"group": group_name, "total": 0, "items": []}
                )
                group["items"].append({"name": acct.name, "amount": round(abs(balance), 2)})
            for group in groups.values():
                group["total"] = round(sum(i["amount"] for i in group["items"]), 2)
            return list(groups.values())

        liabilities = group_accounts(Account.AccountType.LIABILITY)
        assets = group_accounts(Account.AccountType.ASSET)

        total = round(sum(g["total"] for g in liabilities), 2)
        data = {"liabilities": liabilities, "assets": assets, "total": total}
        return Response(data)


class CashFlowViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response(
                {
                    "transactions": [],
                    "opening_balance": 0,
                    "total_inflow": 0,
                    "total_outflow": 0,
                    "net_cash_flow": 0,
                }
            )
        from_date = _parse_date(request.query_params.get("from_date"))
        to_date = _parse_date(request.query_params.get("to_date"))

        receipts = ReceiptVoucher.objects.filter(tenant_id=tenant_id)
        payments = PaymentVoucher.objects.filter(tenant_id=tenant_id)
        opening_receipts = receipts
        opening_payments = payments
        if from_date:
            receipts = receipts.filter(date__gte=from_date)
            payments = payments.filter(date__gte=from_date)
            opening_receipts = opening_receipts.filter(date__lt=from_date)
            opening_payments = opening_payments.filter(date__lt=from_date)
        if to_date:
            receipts = receipts.filter(date__lte=to_date)
            payments = payments.filter(date__lte=to_date)
            opening_receipts = opening_receipts.filter(date__lte=to_date)
            opening_payments = opening_payments.filter(date__lte=to_date)

        rows = []
        for r in receipts.select_related("party"):
            rows.append(
                {
                    "date": r.date,
                    "type": "Receipt",
                    "voucher_number": r.voucher_number,
                    "ledger": r.party.name,
                    "cash_in": float(r.amount),
                    "cash_out": 0,
                }
            )
        for p in payments.select_related("party"):
            rows.append(
                {
                    "date": p.date,
                    "type": "Payment",
                    "voucher_number": p.voucher_number,
                    "ledger": p.party.name,
                    "cash_in": 0,
                    "cash_out": float(p.amount),
                }
            )
        rows.sort(key=lambda x: (x["date"], x["type"]))

        total_inflow = sum(x["cash_in"] for x in rows)
        total_outflow = sum(x["cash_out"] for x in rows)
        opening_balance = float(
            (opening_receipts.aggregate(t=Sum("amount"))["t"] or 0)
            - (opening_payments.aggregate(t=Sum("amount"))["t"] or 0)
        )

        return Response(
            {
                "transactions": rows,
                "opening_balance": round(opening_balance, 2),
                "total_inflow": round(total_inflow, 2),
                "total_outflow": round(total_outflow, 2),
                "net_cash_flow": round(total_inflow - total_outflow, 2),
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


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


class LedgerViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    _VOUCHER_LABELS = {
        "SalesInvoice": "Sales",
        "PurchaseBill": "Purchase",
        "ReceiptVoucher": "Receipt",
        "PaymentVoucher": "Payment",
        "JournalVoucher": "Journal",
        "CreditNote": "Credit Note",
        "DebitNote": "Debit Note",
        "ContraVoucher": "Contra",
        "SaleOrder": "Sale Order",
        "PurchaseOrder": "Purchase Order",
        "DeliveryChallan": "Delivery Challan",
        "SaleReturn": "Sale Return",
        "PurchaseReturn": "Purchase Return",
    }

    @staticmethod
    def _describe_voucher(voucher):
        if voucher is None:
            return {
                "voucher_type": "",
                "voucher_no": "",
                "narration": "",
                "invoice_no": "",
            }
        model_name = type(voucher).__name__
        voucher_no = (
            getattr(voucher, "voucher_number", "")
            or getattr(voucher, "order_number", "")
            or getattr(voucher, "challan_number", "")
            or getattr(voucher, "return_number", "")
        )
        narration = getattr(voucher, "narration", "") or getattr(voucher, "reason", "")
        invoice_no = getattr(voucher, "bill_id", "") or getattr(voucher, "bill_number", "")
        return {
            "voucher_type": LedgerViewSet._VOUCHER_LABELS.get(model_name, model_name),
            "voucher_no": voucher_no,
            "narration": narration,
            "invoice_no": invoice_no,
        }

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
        parsed_from = _parse_date(from_date)
        parsed_to = _parse_date(to_date)
        if parsed_from:
            qs = qs.filter(date__gte=parsed_from)
        if parsed_to:
            qs = qs.filter(date__lte=parsed_to)

        rows = []
        for entry in qs.select_related("account").all():
            rows.append(
                {
                    "date": entry.date,
                    "debit": float(entry.debit or 0),
                    "credit": float(entry.credit or 0),
                    "account": entry.account.name,
                    "voucher": entry.voucher,
                    "id": entry.uuid,
                }
            )

        if account_id:
            party_ids = Party.objects.filter(account_id=account_id).values_list("id", flat=True)
            if party_ids:
                synthetic = self._collect_unposted_vouchers(
                    tenant_id, party_ids, parsed_from, parsed_to
                )
                rows.extend(synthetic)

        data = []
        running_balance = 0
        for row in sorted(rows, key=lambda r: str(r["date"])):
            debit = row["debit"]
            credit = row["credit"]
            running_balance += debit - credit
            details = LedgerViewSet._describe_voucher(row["voucher"])
            data.append(
                {
                    "id": row["id"],
                    "date": row["date"],
                    "account": row["account"],
                    "debit": debit,
                    "credit": credit,
                    "balance": running_balance,
                    "dr_cr": "Dr" if debit > 0 else "Cr",
                    "voucher_type": details["voucher_type"],
                    "voucher_no": details["voucher_no"],
                    "narration": details["narration"],
                    "invoice_no": details["invoice_no"],
                }
            )
        return Response(data)

    @staticmethod
    def _collect_unposted_vouchers(tenant_id, party_ids, parsed_from, parsed_to):
        rows = []

        def push(model, dr_attr, cr_attr, posted_kwargs=None):
            if posted_kwargs is None:
                posted_kwargs = {"is_posted": False}
            qs = model.objects.filter(party_id__in=party_ids, **posted_kwargs)
            if parsed_from:
                qs = qs.filter(date__gte=parsed_from)
            if parsed_to:
                qs = qs.filter(date__lte=parsed_to)
            for v in qs.select_related("party"):
                rows.append(
                    {
                        "date": v.date,
                        "debit": float(getattr(v, dr_attr) or 0) if dr_attr else 0,
                        "credit": float(getattr(v, cr_attr) or 0) if cr_attr else 0,
                        "account": v.party.account.name if v.party and v.party.account else "",
                        "voucher": v,
                        "id": v.uuid,
                    }
                )

        push(SalesInvoice, "total_amount", None)
        push(PurchaseBill, None, "total_amount")
        push(CreditNote, None, "total_amount")
        push(DebitNote, "total_amount", None)
        push(SaleReturn, None, "total_amount", posted_kwargs={})
        push(PurchaseReturn, "total_amount", None, posted_kwargs={})
        push(ReceiptVoucher, None, "amount")
        push(PaymentVoucher, "amount", None)
        return rows


# =====================
# MISSING REPORT VIEWS
# =====================


def _date_filter(qs, request, date_field="date"):
    from_date = _parse_date(request.query_params.get("from_date"))
    to_date = _parse_date(request.query_params.get("to_date"))
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

        invoice_rates = {
            row["invoice_id"]: float(row["m"] or 0)
            for row in SalesInvoiceItem.objects.filter(invoice__in=qs)
            .values("invoice_id")
            .annotate(m=Max("gst_rate"))
        }
        hsn_map = {}
        for item in SalesInvoiceItem.objects.filter(invoice__in=qs).select_related("item"):
            hsn = item.item.hsn_code if item.item else "UNKNOWN"
            row = hsn_map.setdefault(
                hsn,
                {
                    "hsn_code": hsn,
                    "description": item.item.name if item.item else "",
                    "taxable_value": 0,
                    "total_gst": 0,
                    "gst_rate": 0,
                },
            )
            row["taxable_value"] += float(item.taxable_value)
            row["total_gst"] += (
                float(item.cgst) + float(item.sgst) + float(item.igst) + float(item.cess)
            )
            row["gst_rate"] = float(item.gst_rate or 0) or row["gst_rate"]

        data = []
        for inv in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(inv.uuid),
                    "date": inv.date,
                    "party_name": inv.party.name if inv.party else "",
                    "gstin": inv.party.gstin if inv.party else "",
                    "address": inv.party.billing_address if inv.party else "",
                    "supply_type": inv.supply_type,
                    "narration": inv.narration,
                    "voucher_number": inv.voucher_number,
                    "bill_id": inv.bill_id or "",
                    "total_amount": float(inv.total_amount),
                    "total_taxable_amount": float(inv.total_taxable_amount),
                    "total_cgst": float(inv.total_cgst),
                    "total_sgst": float(inv.total_sgst),
                    "total_igst": float(inv.total_igst),
                    "gst_rate": invoice_rates.get(inv.id, 0),
                    "paid": float(inv.paid),
                    "balance": float(inv.balance),
                    "is_posted": inv.is_posted,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response(
            {
                "sales": data,
                "hsn": list(hsn_map.values()),
                "total": float(total),
                "count": len(data),
            }
        )


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

        invoice_rates = {
            row["bill_id"]: float(row["m"] or 0)
            for row in PurchaseBillItem.objects.filter(bill__in=qs)
            .values("bill_id")
            .annotate(m=Max("gst_rate"))
        }
        hsn_map = {}
        for item in PurchaseBillItem.objects.filter(bill__in=qs).select_related("item"):
            hsn = item.item.hsn_code if item.item else "UNKNOWN"
            row = hsn_map.setdefault(
                hsn,
                {
                    "hsn_code": hsn,
                    "description": item.item.name if item.item else "",
                    "taxable_value": 0,
                    "total_gst": 0,
                    "gst_rate": 0,
                },
            )
            row["taxable_value"] += float(item.taxable_value)
            row["total_gst"] += (
                float(item.cgst) + float(item.sgst) + float(item.igst) + float(item.cess)
            )
            row["gst_rate"] = float(item.gst_rate or 0) or row["gst_rate"]

        data = []
        for bill in qs.select_related("party").order_by("date"):
            data.append(
                {
                    "id": str(bill.uuid),
                    "date": bill.date,
                    "party_name": bill.party.name if bill.party else "",
                    "gstin": bill.party.gstin if bill.party else "",
                    "address": bill.party.billing_address if bill.party else "",
                    "supply_type": bill.supply_type,
                    "narration": bill.narration,
                    "voucher_number": bill.voucher_number,
                    "bill_id": bill.bill_id or "",
                    "total_amount": float(bill.total_amount),
                    "total_taxable_amount": float(bill.total_taxable_amount),
                    "total_cgst": float(bill.total_cgst),
                    "total_sgst": float(bill.total_sgst),
                    "total_igst": float(bill.total_igst),
                    "gst_rate": invoice_rates.get(bill.id, 0),
                    "paid": float(bill.paid),
                    "balance": float(bill.balance),
                    "is_posted": bill.is_posted,
                }
            )
        total = qs.aggregate(t=Sum("total_amount"))["t"] or 0
        return Response(
            {
                "purchases": data,
                "hsn": list(hsn_map.values()),
                "total": float(total),
                "count": len(data),
            }
        )


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
        for ret in (
            qs.select_related("party", "invoice").prefetch_related("items").order_by("date")
        ):
            taxable = sum(float(i.taxable_value or 0) for i in ret.items.all())
            total_gst = sum(
                float(i.cgst or 0) + float(i.sgst or 0) + float(i.igst or 0) + float(i.cess or 0)
                for i in ret.items.all()
            )
            item_rows = [
                {
                    "hsn_code": i.item.hsn_code if i.item else "",
                    "hsn_description": i.item.name if i.item else "",
                    "quantity": float(i.quantity),
                    "unit_price": float(i.price),
                    "taxable_value": float(i.taxable_value),
                    "gst_rate": float(i.gst_rate),
                    "total_gst": float(i.cgst) + float(i.sgst) + float(i.igst) + float(i.cess),
                    "amount": float(i.amount),
                }
                for i in ret.items.all()
            ]
            data.append(
                {
                    "id": str(ret.uuid),
                    "date": ret.date,
                    "return_number": ret.return_number,
                    "party_name": ret.party.name if ret.party else "",
                    "gstin": ret.party.gstin if ret.party else "",
                    "customer_address": ret.party.billing_address if ret.party else "",
                    "invoice_number": ret.invoice.bill_id if ret.invoice else "",
                    "total_amount": float(ret.total_amount),
                    "taxable_value": round(taxable, 2),
                    "total_gst": round(total_gst, 2),
                    "reason": ret.reason,
                    "items": item_rows,
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
        for ret in qs.select_related("party", "bill").prefetch_related("items").order_by("date"):
            taxable = sum(float(i.taxable_value or 0) for i in ret.items.all())
            total_gst = sum(
                float(i.cgst or 0) + float(i.sgst or 0) + float(i.igst or 0) + float(i.cess or 0)
                for i in ret.items.all()
            )
            item_rows = [
                {
                    "hsn_code": i.item.hsn_code if i.item else "",
                    "hsn_description": i.item.name if i.item else "",
                    "quantity": float(i.quantity),
                    "unit_price": float(i.price),
                    "taxable_value": float(i.taxable_value),
                    "gst_rate": float(i.gst_rate),
                    "total_gst": float(i.cgst) + float(i.sgst) + float(i.igst) + float(i.cess),
                    "amount": float(i.amount),
                }
                for i in ret.items.all()
            ]
            data.append(
                {
                    "id": str(ret.uuid),
                    "date": ret.date,
                    "return_number": ret.return_number,
                    "party_name": ret.party.name if ret.party else "",
                    "gstin": ret.party.gstin if ret.party else "",
                    "vendor_address": ret.party.billing_address if ret.party else "",
                    "bill_number": ret.bill.bill_id if ret.bill else "",
                    "total_amount": float(ret.total_amount),
                    "taxable_value": round(taxable, 2),
                    "total_gst": round(total_gst, 2),
                    "reason": ret.reason,
                    "items": item_rows,
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

        def supply_type_label(value):
            return {
                "REGULAR": "Regular",
                "SEZ": "SEZ Supply",
                "EXPORT": "Export",
            }.get(value, value or "")

        def order_status_label(value):
            return {
                "PENDING": "Pending",
                "CONFIRMED": "Complete",
                "CANCELLED": "Cancelled",
            }.get(value, value or "")

        data = []
        for order in qs.select_related("party").prefetch_related("items").order_by("date"):
            taxable = sum(float(i.taxable_value or 0) for i in order.items.all())
            total_cgst = sum(float(i.cgst or 0) for i in order.items.all())
            total_sgst = sum(float(i.sgst or 0) for i in order.items.all())
            total_igst = sum(float(i.igst or 0) for i in order.items.all())
            gst_rate = max((float(i.gst_rate or 0) for i in order.items.all()), default=0)
            data.append(
                {
                    "id": str(order.uuid),
                    "date": order.date,
                    "order_number": order.order_number,
                    "party_name": order.party.name if order.party else "",
                    "customer_gstin": order.party.gstin if order.party else "",
                    "billing_address": order.party.billing_address if order.party else "",
                    "shipping_address": order.party.shipping_address if order.party else "",
                    "supply_type": supply_type_label(order.supply_type),
                    "narration": order.narration,
                    "total_amount": float(order.total_amount),
                    "taxable_value": round(taxable, 2),
                    "total_gst": round(total_cgst + total_sgst + total_igst, 2),
                    "total_cgst": round(total_cgst, 2),
                    "total_sgst": round(total_sgst, 2),
                    "total_igst": round(total_igst, 2),
                    "gst_rate": gst_rate,
                    "item_count": order.items.count(),
                    "status": order_status_label(order.status),
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

        def challan_type_label(value):
            return {
                "SALES": "Sales",
                "PURCHASE_RETURN": "Purchase Return",
                "JOB_WORK": "Job Work",
                "FREE": "Free",
            }.get(value, value or "")

        def status_label(value):
            return {
                "DRAFT": "Pending",
                "DELIVERED": "Complete",
                "CANCELLED": "Cancelled",
            }.get(value, value or "")

        data = []
        for dc in qs.select_related("party").prefetch_related("items").order_by("date"):
            taxable = sum(float(i.taxable_value or 0) for i in dc.items.all())
            total_cgst = sum(float(i.cgst or 0) for i in dc.items.all())
            total_sgst = sum(float(i.sgst or 0) for i in dc.items.all())
            total_igst = sum(float(i.igst or 0) for i in dc.items.all())
            gst_rate = max((float(i.gst_rate or 0) for i in dc.items.all()), default=0)
            transport = " ".join(filter(None, [dc.transporter_name, dc.vehicle_no, dc.lr_rr_no]))
            data.append(
                {
                    "id": str(dc.uuid),
                    "date": dc.date,
                    "challan_number": dc.challan_number,
                    "challan_type": challan_type_label(dc.challan_type),
                    "raw_challan_type": dc.challan_type,
                    "party_name": dc.party.name if dc.party else "",
                    "customer_gstin": dc.party.gstin if dc.party else "",
                    "billing_address": dc.party.billing_address if dc.party else "",
                    "shipping_address": dc.party.shipping_address if dc.party else "",
                    "total_amount": float(dc.total_amount),
                    "taxable_value": round(taxable, 2),
                    "total_gst": round(total_cgst + total_sgst + total_igst, 2),
                    "total_cgst": round(total_cgst, 2),
                    "total_sgst": round(total_sgst, 2),
                    "total_igst": round(total_igst, 2),
                    "gst_rate": gst_rate,
                    "transporter_name": dc.transporter_name or "",
                    "vehicle_no": dc.vehicle_no or "",
                    "lr_rr_no": dc.lr_rr_no or "",
                    "transport_details": transport,
                    "item_count": dc.items.count(),
                    "status": status_label(dc.status),
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
                    "unit": item.primary_unit or "",
                    "opening_quantity": float(item.opening_quantity or 0),
                    "sale_quantity": float(sale_qty),
                    "purchase_quantity": float(purchase_qty),
                    "closing_quantity": float(
                        (item.opening_quantity or 0) + purchase_qty - sale_qty
                    ),
                    "sale_price": float(item.sale_price or 0),
                    "purchase_price": float(item.purchase_price or 0),
                    "rate": float(item.purchase_price or item.at_price or 0),
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

        type_param = (request.query_params.get("type") or "").lower()
        include_sale = not type_param or "purchase" not in type_param
        include_purchase = not type_param or "sale" not in type_param

        sale_items = SalesInvoiceItem.objects.all()
        purchase_items = PurchaseBillItem.objects.all()
        sale_items = sale_items.filter(invoice__tenant_id=tenant_id)
        purchase_items = purchase_items.filter(bill__tenant_id=tenant_id)
        sale_items = _date_filter(sale_items, request, date_field="invoice__date")
        purchase_items = _date_filter(purchase_items, request, date_field="bill__date")

        hsn_map = {}

        def blank(hsn, name, unit):
            return {
                "hsn_code": hsn,
                "item_name": name,
                "description": name,
                "unit": unit or "",
                "rate": 0,
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

        if include_sale:
            for si in sale_items.select_related("item"):
                hsn = si.item.hsn_code if si.item else "UNKNOWN"
                row = hsn_map.setdefault(
                    hsn,
                    blank(
                        hsn,
                        si.item.name if si.item else "",
                        si.item.primary_unit if si.item else "",
                    ),
                )
                row["rate"] = float(si.gst_rate or 0) or row["rate"]
                row["sale_quantity"] += float(si.quantity)
                row["sale_taxable_value"] += float(si.taxable_value)
                row["sale_cgst"] += float(si.cgst)
                row["sale_sgst"] += float(si.sgst)
                row["sale_igst"] += float(si.igst)

        if include_purchase:
            for pi in purchase_items.select_related("item"):
                hsn = pi.item.hsn_code if pi.item else "UNKNOWN"
                row = hsn_map.setdefault(
                    hsn,
                    blank(
                        hsn,
                        pi.item.name if pi.item else "",
                        pi.item.primary_unit if pi.item else "",
                    ),
                )
                row["rate"] = float(pi.gst_rate or 0) or row["rate"]
                row["purchase_quantity"] += float(pi.quantity)
                row["purchase_taxable_value"] += float(pi.taxable_value)
                row["purchase_cgst"] += float(pi.cgst)
                row["purchase_sgst"] += float(pi.sgst)
                row["purchase_igst"] += float(pi.igst)

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

        parsed_from = _parse_date(request.query_params.get("from_date"))
        parsed_to = _parse_date(request.query_params.get("to_date"))
        single_date = _parse_date(request.query_params.get("date"))
        vtype = (request.query_params.get("voucher_type") or "").strip().lower()

        def in_range(qs, date_field="date"):
            if single_date:
                qs = qs.filter(**{f"{date_field}": single_date})
            else:
                if parsed_from:
                    qs = qs.filter(**{f"{date_field}__gte": parsed_from})
                if parsed_to:
                    qs = qs.filter(**{f"{date_field}__lte": parsed_to})
            return qs

        entries = []

        def push(
            vtype_label,
            qs,
            number_attr,
            amount_attr,
            side,
            narration_attr="narration",
            invoice_attr=None,
        ):
            if vtype and vtype != vtype_label:
                return
            for obj in qs:
                party = getattr(obj, "party", None)
                number = getattr(obj, number_attr, "") or ""
                narration = getattr(obj, narration_attr, "") or ""
                invoice_no = ""
                if invoice_attr:
                    invoice_no = getattr(obj, invoice_attr, "") or ""
                amount = float(getattr(obj, amount_attr) or 0)
                entries.append(
                    {
                        "id": str(obj.uuid),
                        "date": obj.date,
                        "party_name": party.name if party else "",
                        "party": party.name if party else "",
                        "ledger_name": party.name if party else "",
                        "voucher_type": vtype_label,
                        "voucher_no": number,
                        "invoice_no": invoice_no,
                        "narration": narration,
                        "paid_amount": amount if side == "dr" else 0.0,
                        "received_amount": amount if side == "cr" else 0.0,
                        "debit": amount if side == "dr" else 0.0,
                        "credit": amount if side == "cr" else 0.0,
                    }
                )

        push(
            "sale",
            in_range(SalesInvoice.objects.filter(tenant_id=tenant_id).select_related("party")),
            "voucher_number",
            "total_amount",
            "dr",
            invoice_attr="bill_id",
        )
        push(
            "purchase",
            in_range(PurchaseBill.objects.filter(tenant_id=tenant_id).select_related("party")),
            "voucher_number",
            "total_amount",
            "cr",
            invoice_attr="bill_id",
        )
        push(
            "receipt",
            in_range(ReceiptVoucher.objects.filter(tenant_id=tenant_id).select_related("party")),
            "voucher_number",
            "amount",
            "cr",
        )
        push(
            "payment",
            in_range(PaymentVoucher.objects.filter(tenant_id=tenant_id).select_related("party")),
            "voucher_number",
            "amount",
            "dr",
        )
        push(
            "credit note",
            in_range(CreditNote.objects.filter(tenant_id=tenant_id).select_related("party")),
            "voucher_number",
            "total_amount",
            "cr",
            invoice_attr="bill_id",
        )
        push(
            "debit note",
            in_range(DebitNote.objects.filter(tenant_id=tenant_id).select_related("party")),
            "voucher_number",
            "total_amount",
            "dr",
            invoice_attr="bill_id",
        )
        push(
            "contra",
            in_range(ContraVoucher.objects.filter(tenant_id=tenant_id)),
            "voucher_number",
            "amount",
            "cr",
        )
        if not vtype or vtype == "journal":
            for jv in in_range(JournalVoucher.objects.filter(tenant_id=tenant_id)):
                dr = sum(float(e.debit or 0) for e in jv.entries.all())
                cr = sum(float(e.credit or 0) for e in jv.entries.all())
                entries.append(
                    {
                        "id": str(jv.uuid),
                        "date": jv.date,
                        "party_name": "",
                        "party": "",
                        "ledger_name": "",
                        "voucher_type": "journal",
                        "voucher_no": jv.voucher_number,
                        "invoice_no": "",
                        "narration": jv.narration or "",
                        "paid_amount": dr,
                        "received_amount": cr,
                        "debit": dr,
                        "credit": cr,
                    }
                )

        entries.sort(key=lambda e: e["date"], reverse=True)
        total_received = sum(e["received_amount"] for e in entries)
        total_paid = sum(e["paid_amount"] for e in entries)
        return Response(
            {
                "entries": entries,
                "total_received": round(total_received, 2),
                "total_paid": round(total_paid, 2),
                "net": round(total_received - total_paid, 2),
                "count": len(entries),
            }
        )


class CashBankBookViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request):
        tenant_id = _get_tenant_or_empty(request)
        if tenant_id is None:
            return Response({"entries": [], "summary": {"cash": [], "bank": []}})

        parsed_from = _parse_date(request.query_params.get("from_date"))
        parsed_to = _parse_date(request.query_params.get("to_date"))
        book_type = (request.query_params.get("account_type") or "both").strip().lower()

        def in_range(qs, date_field="date"):
            if parsed_from:
                qs = qs.filter(**{f"{date_field}__gte": parsed_from})
            if parsed_to:
                qs = qs.filter(**{f"{date_field}__lte": parsed_to})
            return qs

        accounts = Account.objects.filter(
            tenant_id=tenant_id, account_type=Account.AccountType.ASSET
        )
        cash_accounts = [a for a in accounts if "cash" in (a.name or "").lower()]
        bank_accounts = [a for a in accounts if "bank" in (a.name or "").lower()]
        all_ids = [a.id for a in cash_accounts + bank_accounts]

        if book_type == "cash":
            selected_ids = [a.id for a in cash_accounts]
        elif book_type == "bank":
            selected_ids = [a.id for a in bank_accounts]
        else:
            selected_ids = all_ids

        def selected(account_id):
            return account_id in selected_ids

        entries = []

        for entry in (
            in_range(Ledger.objects.filter(account_id__in=selected_ids))
            .select_related("account")
            .order_by("date")
        ):
            details = LedgerViewSet._describe_voucher(entry.voucher)
            entries.append(
                {
                    "date": entry.date,
                    "account": entry.account.name,
                    "particulars": entry.account.name,
                    "voucher_type": details["voucher_type"],
                    "voucher_no": details["voucher_no"],
                    "debit": float(entry.debit or 0),
                    "credit": float(entry.credit or 0),
                }
            )

        for rv in (
            in_range(ReceiptVoucher.objects.filter(tenant_id=tenant_id, is_posted=False))
            .select_related("party", "received_in")
            .order_by("date")
        ):
            if not selected(rv.received_in_id):
                continue
            entries.append(
                {
                    "date": rv.date,
                    "account": rv.received_in.name,
                    "particulars": rv.party.name if rv.party else rv.received_in.name,
                    "voucher_type": "Receipt",
                    "voucher_no": rv.voucher_number,
                    "debit": 0.0,
                    "credit": float(rv.amount),
                }
            )

        for pv in (
            in_range(PaymentVoucher.objects.filter(tenant_id=tenant_id, is_posted=False))
            .select_related("party", "paid_from")
            .order_by("date")
        ):
            if not selected(pv.paid_from_id):
                continue
            entries.append(
                {
                    "date": pv.date,
                    "account": pv.paid_from.name,
                    "particulars": pv.party.name if pv.party else pv.paid_from.name,
                    "voucher_type": "Payment",
                    "voucher_no": pv.voucher_number,
                    "debit": float(pv.amount),
                    "credit": 0.0,
                }
            )

        for cv in (
            in_range(ContraVoucher.objects.filter(tenant_id=tenant_id, is_posted=False))
            .select_related("from_account", "to_account")
            .order_by("date")
        ):
            if selected(cv.from_account_id):
                entries.append(
                    {
                        "date": cv.date,
                        "account": cv.from_account.name,
                        "particulars": cv.from_account.name,
                        "voucher_type": "Contra",
                        "voucher_no": cv.voucher_number,
                        "debit": float(cv.amount),
                        "credit": 0.0,
                    }
                )
            if selected(cv.to_account_id):
                entries.append(
                    {
                        "date": cv.date,
                        "account": cv.to_account.name,
                        "particulars": cv.to_account.name,
                        "voucher_type": "Contra",
                        "voucher_no": cv.voucher_number,
                        "debit": 0.0,
                        "credit": float(cv.amount),
                    }
                )

        entries.sort(key=lambda e: (str(e["date"]), e["account"]))

        def build_summary(account_list):
            items = []
            for account in account_list:
                dr = sum(e["debit"] for e in entries if e["account"] == account.name)
                cr = sum(e["credit"] for e in entries if e["account"] == account.name)
                items.append({"name": account.name, "dr": round(dr, 2), "cr": round(cr, 2)})
            return items

        return Response(
            {
                "entries": entries,
                "summary": {
                    "cash": build_summary(cash_accounts),
                    "bank": build_summary(bank_accounts),
                },
            }
        )
