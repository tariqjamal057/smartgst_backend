from rest_framework import serializers

from .models import (
    Account,
    BankReconciliation,
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


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = "__all__"


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = "__all__"


class ItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCategory
        fields = "__all__"


class ItemSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=ItemCategory.objects.all(), required=False, allow_null=True
    )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.category:
            representation["category"] = ItemCategorySerializer(instance.category).data
        return representation

    class Meta:
        model = Item
        fields = "__all__"


class FinancialYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialYear
        fields = "__all__"


# --- Sales Invoice Serializers ---
class SalesInvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesInvoiceItem
        fields = [
            "item",
            "mrp",
            "quantity",
            "unit",
            "price",
            "price_type",
            "discount_percentage",
            "discount_amount",
            "taxable_value",
            "gst_rate",
            "cgst",
            "sgst",
            "igst",
            "cess",
            "amount",
        ]


class SalesInvoiceSerializer(serializers.ModelSerializer):
    items = SalesInvoiceItemSerializer(many=True)

    class Meta:
        model = SalesInvoice
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        invoice = SalesInvoice.objects.create(**validated_data)
        for item_data in items_data:
            SalesInvoiceItem.objects.create(invoice=invoice, **item_data)

        Transaction.objects.create(
            party=invoice.party,
            voucher_type="SALES",
            transaction_type=Transaction.TransactionTypeChoices.SALE,
            receipt_no=invoice.bill_id or invoice.voucher_number,
            date=invoice.bill_date or invoice.date,
            payment_type=invoice.payment_type,
            received_amount=invoice.paid,
        )
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                SalesInvoiceItem.objects.create(invoice=instance, **item_data)

        return instance


# --- Purchase Bill Serializers ---
class PurchaseBillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseBillItem
        fields = [
            "item",
            "mrp",
            "quantity",
            "unit",
            "price",
            "price_type",
            "discount_percentage",
            "discount_amount",
            "taxable_value",
            "gst_rate",
            "cgst",
            "sgst",
            "igst",
            "cess",
            "amount",
        ]


class PurchaseBillSerializer(serializers.ModelSerializer):
    items = PurchaseBillItemSerializer(many=True)

    class Meta:
        model = PurchaseBill
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        bill = PurchaseBill.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseBillItem.objects.create(bill=bill, **item_data)

        Transaction.objects.create(
            party=bill.party,
            voucher_type="PURCHASE",
            transaction_type=Transaction.TransactionTypeChoices.PURCHASE,
            receipt_no=bill.bill_id or bill.voucher_number,
            date=bill.bill_date or bill.date,
            payment_type=bill.payment_type,
            paid_amount=bill.paid,
        )
        return bill

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseBillItem.objects.create(bill=instance, **item_data)

        return instance


# --- Other Voucher Serializers ---
class ReceiptVoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptVoucher
        fields = "__all__"


class PaymentVoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentVoucher
        fields = "__all__"


class JournalVoucherEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalVoucherEntry
        fields = ["account", "debit", "credit"]


class JournalVoucherSerializer(serializers.ModelSerializer):
    entries = JournalVoucherEntrySerializer(many=True)

    class Meta:
        model = JournalVoucher
        fields = "__all__"

    def validate(self, data):
        entries_data = data.get("entries")
        if not entries_data:
            raise serializers.ValidationError("Journal voucher must have at least one entry.")

        total_debit = sum(entry.get("debit", 0) for entry in entries_data)
        total_credit = sum(entry.get("credit", 0) for entry in entries_data)

        if total_debit != total_credit:
            raise serializers.ValidationError("Total debits must equal total credits.")

        if total_debit == 0:
            raise serializers.ValidationError("Journal voucher amount cannot be zero.")

        return data

    def create(self, validated_data):
        entries_data = validated_data.pop("entries")
        journal = JournalVoucher.objects.create(**validated_data)
        for entry_data in entries_data:
            JournalVoucherEntry.objects.create(voucher=journal, **entry_data)
        return journal


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"


class InvoiceSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSetting
        fields = "__all__"


# --- Sale Order ---
class SaleOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleOrderItem
        fields = "__all__"


class SaleOrderSerializer(serializers.ModelSerializer):
    items = SaleOrderItemSerializer(many=True)

    class Meta:
        model = SaleOrder
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = SaleOrder.objects.create(**validated_data)
        for item_data in items_data:
            SaleOrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                SaleOrderItem.objects.create(order=instance, **item_data)
        return instance


# --- Purchase Order ---
class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)

    class Meta:
        model = PurchaseOrder
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = PurchaseOrder.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseOrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseOrderItem.objects.create(order=instance, **item_data)
        return instance


# --- Delivery Challan ---
class DeliveryChallanItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryChallanItem
        fields = "__all__"


class DeliveryChallanSerializer(serializers.ModelSerializer):
    items = DeliveryChallanItemSerializer(many=True)

    class Meta:
        model = DeliveryChallan
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        challan = DeliveryChallan.objects.create(**validated_data)
        for item_data in items_data:
            DeliveryChallanItem.objects.create(challan=challan, **item_data)
        return challan

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                DeliveryChallanItem.objects.create(challan=instance, **item_data)
        return instance


# --- Contra Voucher ---
class ContraVoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContraVoucher
        fields = "__all__"


# --- Credit Note ---
class CreditNoteItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNoteItem
        fields = "__all__"


class CreditNoteSerializer(serializers.ModelSerializer):
    items = CreditNoteItemSerializer(many=True)

    class Meta:
        model = CreditNote
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        note = CreditNote.objects.create(**validated_data)
        for item_data in items_data:
            CreditNoteItem.objects.create(credit_note=note, **item_data)
        return note

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                CreditNoteItem.objects.create(credit_note=instance, **item_data)
        return instance


# --- Debit Note ---
class DebitNoteItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebitNoteItem
        fields = "__all__"


class DebitNoteSerializer(serializers.ModelSerializer):
    items = DebitNoteItemSerializer(many=True)

    class Meta:
        model = DebitNote
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        note = DebitNote.objects.create(**validated_data)
        for item_data in items_data:
            DebitNoteItem.objects.create(debit_note=note, **item_data)
        return note

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                DebitNoteItem.objects.create(debit_note=instance, **item_data)
        return instance


# --- Document ---
class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"


# --- Sale Return ---
class SaleReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleReturnItem
        fields = "__all__"


class SaleReturnSerializer(serializers.ModelSerializer):
    items = SaleReturnItemSerializer(many=True)

    class Meta:
        model = SaleReturn
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        obj = SaleReturn.objects.create(**validated_data)
        for item_data in items_data:
            SaleReturnItem.objects.create(sale_return=obj, **item_data)
        return obj

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                SaleReturnItem.objects.create(sale_return=instance, **item_data)
        return instance


# --- Purchase Return ---
class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseReturnItem
        fields = "__all__"


class PurchaseReturnSerializer(serializers.ModelSerializer):
    items = PurchaseReturnItemSerializer(many=True)

    class Meta:
        model = PurchaseReturn
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        obj = PurchaseReturn.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseReturnItem.objects.create(purchase_return=obj, **item_data)
        return obj

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseReturnItem.objects.create(purchase_return=instance, **item_data)
        return instance


# --- Bank Reconciliation ---
class BankReconciliationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankReconciliation
        fields = "__all__"
