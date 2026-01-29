from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import (
    Account,
    FinancialYear,
    Item,
    ItemCategory,
    JournalVoucher,
    Party,
    PaymentVoucher,
    PurchaseBill,
    ReceiptVoucher,
    SalesInvoice,
)
from .serializers import (
    AccountSerializer,
    FinancialYearSerializer,
    ItemCategorySerializer,
    ItemSerializer,
    JournalVoucherSerializer,
    PartySerializer,
    PaymentVoucherSerializer,
    PurchaseBillSerializer,
    ReceiptVoucherSerializer,
    SalesInvoiceSerializer,
)


class BaseVoucherViewSet(viewsets.ModelViewSet):
    """Base ViewSet for vouchers that enforces financial year and posted status locks."""

    def perform_create(self, serializer):
        financial_year = serializer.validated_data.get("financial_year")
        if financial_year and financial_year.is_locked:
            raise ValidationError(f"Financial year {financial_year} is locked.")
        serializer.save()

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
        """Posts the voucher to the ledger."""
        voucher = self.get_object()
        if voucher.is_posted:
            return Response(
                {"detail": "This voucher has already been posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        services.post_voucher(voucher)
        return Response({"detail": "Voucher posted successfully."}, status=status.HTTP_200_OK)


class FinancialYearViewSet(viewsets.ModelViewSet):
    """API endpoint that allows financial years to be viewed or edited."""

    queryset = FinancialYear.objects.all()
    serializer_class = FinancialYearSerializer


class AccountViewSet(viewsets.ModelViewSet):
    """API endpoint that allows accounts to be viewed or edited."""

    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class PartyViewSet(viewsets.ModelViewSet):
    """API endpoint that allows parties (customers/vendors) to be viewed or edited."""

    queryset = Party.objects.all()
    serializer_class = PartySerializer


class ItemCategoryViewSet(viewsets.ModelViewSet):
    """API endpoint that allows item categories to be viewed or edited."""

    queryset = ItemCategory.objects.all()
    serializer_class = ItemCategorySerializer


class ItemViewSet(viewsets.ModelViewSet):
    """API endpoint that allows items to be viewed or edited."""

    queryset = Item.objects.all()
    serializer_class = ItemSerializer


class SalesInvoiceViewSet(BaseVoucherViewSet):
    """API endpoint that allows sales invoices to be viewed or edited."""

    queryset = SalesInvoice.objects.all()
    serializer_class = SalesInvoiceSerializer


class PurchaseBillViewSet(BaseVoucherViewSet):
    """API endpoint that allows purchase bills to be viewed or edited."""

    queryset = PurchaseBill.objects.all()
    serializer_class = PurchaseBillSerializer


class ReceiptVoucherViewSet(BaseVoucherViewSet):
    """API endpoint that allows receipt vouchers to be viewed or edited."""

    queryset = ReceiptVoucher.objects.all()
    serializer_class = ReceiptVoucherSerializer


class PaymentVoucherViewSet(BaseVoucherViewSet):
    """API endpoint that allows payment vouchers to be viewed or edited."""

    queryset = PaymentVoucher.objects.all()
    serializer_class = PaymentVoucherSerializer


class JournalVoucherViewSet(BaseVoucherViewSet):
    """API endpoint that allows journal vouchers to be viewed or edited."""

    queryset = JournalVoucher.objects.all()
    serializer_class = JournalVoucherSerializer
