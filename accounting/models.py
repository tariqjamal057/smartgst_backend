from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseModel


class FinancialYear(BaseModel):
    """Represents a financial year for a tenant to lock periods."""

    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name_plural = "Financial Years"
        ordering = ["-start_date"]


class Account(BaseModel):
    """Represents an account in the Chart of Accounts."""

    class AccountType(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"
        EQUITY = "EQUITY", "Equity"
        REVENUE = "REVENUE", "Revenue"
        EXPENSE = "EXPENSE", "Expense"

    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=10, choices=AccountType.choices)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Chart of Accounts"
        unique_together = ("name",)  # Unique per tenant


class Party(BaseModel):
    """Represents a customer, vendor, or other business party."""

    class PartyType(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        VENDOR = "VENDOR", "Vendor"

    name = models.CharField(max_length=100)
    party_type = models.CharField(max_length=10, choices=PartyType.choices)
    gstin = models.CharField(max_length=15, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    address = models.TextField(blank=True)
    account = models.OneToOneField(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="party_account"
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.account:
            # Determine the parent account (control account)
            if self.party_type == self.PartyType.CUSTOMER:
                parent_account_name = "Sundry Debtors"
                parent_account_type = Account.AccountType.ASSET
            else:  # VENDOR
                parent_account_name = "Sundry Creditors"
                parent_account_type = Account.AccountType.LIABILITY

            # Get or create the parent control account
            parent_account, _ = Account.objects.get_or_create(
                name=parent_account_name,
                defaults={"account_type": parent_account_type, "is_default": True},
            )

            # Create the account for the party
            party_account = Account.objects.create(
                name=self.name,
                account_type=parent_account.account_type,
                parent=parent_account,
            )
            self.account = party_account
            self.save(update_fields=["account"])

    class Meta:
        verbose_name_plural = "Parties"


class Item(BaseModel):
    """Represents a product or service."""

    name = models.CharField(max_length=100, unique=True)
    hsn_code = models.CharField(max_length=20, blank=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Items"


class BaseVoucher(BaseModel):
    """Abstract base model for all vouchers."""

    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    voucher_number = models.CharField(max_length=50)
    date = models.DateField()
    narration = models.TextField(blank=True)
    is_posted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True
        unique_together = ("financial_year", "voucher_number")


class SalesInvoice(BaseVoucher):
    customer = models.ForeignKey(
        Party, on_delete=models.PROTECT, limit_choices_to={"party_type": "CUSTOMER"}
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Sales Invoice #{self.voucher_number}"


class SalesInvoiceItem(BaseModel):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=15, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # quantity * rate

    def __str__(self):
        return f"{self.item.name} on Invoice #{self.invoice.voucher_number}"


class PurchaseBill(BaseVoucher):
    vendor = models.ForeignKey(
        Party, on_delete=models.PROTECT, limit_choices_to={"party_type": "VENDOR"}
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Purchase Bill #{self.voucher_number}"


class PurchaseBillItem(BaseModel):
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=15, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # quantity * rate

    def __str__(self):
        return f"{self.item.name} on Bill #{self.bill.voucher_number}"


class ReceiptVoucher(BaseVoucher):
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    received_in = models.ForeignKey(Account, on_delete=models.PROTECT)  # Bank or Cash account
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"Receipt #{self.voucher_number}"


class PaymentVoucher(BaseVoucher):
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    paid_from = models.ForeignKey(Account, on_delete=models.PROTECT)  # Bank or Cash account
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"Payment #{self.voucher_number}"


class JournalVoucher(BaseVoucher):
    pass

    def __str__(self):
        return f"Journal #{self.voucher_number}"


class JournalVoucherEntry(BaseModel):
    """Represents a single entry in a journal voucher."""

    voucher = models.ForeignKey(JournalVoucher, on_delete=models.CASCADE, related_name="entries")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        verbose_name_plural = "Journal Voucher Entries"


class Ledger(BaseModel):
    """Immutable ledger for all double-entry bookkeeping."""

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.UUIDField()
    voucher = GenericForeignKey("content_type", "object_id")

    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    date = models.DateField(db_index=True)

    class Meta:
        verbose_name_plural = "Ledger"
        ordering = ["date"]
