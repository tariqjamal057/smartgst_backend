from rest_framework import serializers

from .models import (
    Account,
    FinancialYear,
    Item,
    ItemCategory,
    JournalVoucher,
    JournalVoucherEntry,
    Party,
    PaymentVoucher,
    PurchaseBill,
    PurchaseBillItem,
    ReceiptVoucher,
    SalesInvoice,
    SalesInvoiceItem,
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
        fields = ["item", "quantity", "rate", "amount"]


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
        return invoice


# --- Purchase Bill Serializers ---
class PurchaseBillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseBillItem
        fields = ["item", "quantity", "rate", "amount"]


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
        return bill


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
