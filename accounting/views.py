from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import (
    Account,
    BankReconciliation,
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
