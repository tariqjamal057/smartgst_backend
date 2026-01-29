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

    class GSTRegistrationTypes(models.TextChoices):
        UNREGISTERED = "UNREGISTERED", "Unregistered"
        CONSUMER = "CONSUMER", "Consumer"
        REGISTERED_BUSINESS_REGULAR = (
            "REGISTERED_BUSINESS_REGULAR",
            "Registered Business (Regular)",
        )
        REGISTERED_BUSINESS_COMPOSITION = (
            "REGISTERED_BUSINESS_COMPOSITION",
            "Registered Business (Composition)",
        )

    name = models.CharField(max_length=100)
    party_type = models.CharField(max_length=10, choices=PartyType.choices)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True)
    gst_type = models.CharField(
        max_length=50,
        choices=GSTRegistrationTypes.choices,
        blank=True,
        default=GSTRegistrationTypes.UNREGISTERED,
        null=True,
    )
    state = models.CharField(max_length=50, blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)
    pan = models.CharField(max_length=10, blank=True)
    account = models.OneToOneField(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="party_account"
    )
    custom_fieds = models.JSONField(blank=True, null=True)

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


class ItemCategory(BaseModel):
    """Represents a category for items."""

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Item Categories"


class Item(BaseModel):
    """Represents a product or service."""

    class PriceType(models.TextChoices):
        WITH_TAX = "WITH_TAX", "With Tax"
        WITHOUT_TAX = "WITHOUT_TAX", "Without Tax"

    class DiscountType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Percentage"
        AMOUNT = "AMOUNT", "Amount"

    class GSTType(models.TextChoices):
        IGST = "IGST", "IGST"
        GST = "GST", "GST"
        EXEMPT = "EXEMPT", "Exempt"

    class ItemUnitType(models.TextChoices):
        NONE = "NONE", "None"
        BOX = "BOX", "Box"
        BAG = "BAG", "Bag"
        BOTTLE = "BOTTLE", "Bottle"
        BUNDLES = "BUNDLES", "Bundles"

    name = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        ItemCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    primary_unit = models.CharField(
        choices=ItemUnitType.choices, default=ItemUnitType.NONE, blank=True, null=True
    )
    secondary_unit = models.CharField(
        choices=ItemUnitType.choices, default=ItemUnitType.NONE, blank=True, null=True
    )
    conversion_rates = models.JSONField(blank=True, null=True)
    image = models.ImageField(upload_to="item_images/", blank=True, null=True)
    code = models.CharField(max_length=50, blank=True, null=True)
    mrp = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    sale_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    sale_price_type = models.CharField(
        max_length=20,
        choices=PriceType.choices,
        default=PriceType.WITHOUT_TAX,
        blank=True,
        null=True,
    )
    discount_value = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    discount_value_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
        blank=True,
        null=True,
    )
    wholesale_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    wholesale_price_type = models.CharField(
        max_length=20, choices=PriceType.choices, blank=True, null=True
    )
    wholesale_purchase_qty = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    purchase_price_type = models.CharField(
        max_length=20, choices=PriceType.choices, blank=True, null=True
    )
    gst_value = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    gst_type = models.CharField(max_length=20, choices=GSTType.choices, blank=True, null=True)
    opening_quantity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    at_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    as_of_date = models.DateField(blank=True, null=True)
    minimum_stock_to_maintain = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    location = models.CharField(max_length=100, blank=True, null=True)

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
    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, null=True, blank=True, related_name="sales_invoices"
    )
    bill_id = models.CharField(max_length=50, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)
    state_of_supply = models.CharField(max_length=50, blank=True, null=True)
    payment_type = models.JSONField(blank=True, null=True)
    round_off_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="invoice/images/", blank=True, null=True)
    documents = models.FileField(upload_to="invoice/documents/", blank=True, null=True)

    def __str__(self):
        return f"Sales Invoice #{self.bill_id}"


class SalesInvoiceItem(BaseModel):

    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    mrp = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, null=True, blank=True
    )
    unit = models.CharField(
        choices=Item.ItemUnitType.choices, default=Item.ItemUnitType.NONE, blank=True, null=True
    )
    price = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )
    price_type = models.CharField(
        max_length=20,
        choices=Item.PriceType.choices,
        default=Item.PriceType.WITHOUT_TAX,
        blank=True,
        null=True,
    )
    discount_percentage = models.CharField(max_length=10, blank=True, null=True)
    discount_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )
    tax_type = models.JSONField(blank=True, null=True)
    tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )

    def __str__(self):
        return f"{self.item.name} on Invoice #{self.invoice.bill_id}"


class PurchaseBill(BaseVoucher):
    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_bills"
    )
    bill_id = models.CharField(max_length=50, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)
    state_of_supply = models.CharField(max_length=50, blank=True, null=True)
    payment_type = models.JSONField(blank=True, null=True)
    round_off_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="purchase/images/", blank=True, null=True)
    documents = models.FileField(upload_to="purchase/documents/", blank=True, null=True)

    def __str__(self):
        return f"Purchase Bill #{self.bill_id}"


class PurchaseBillItem(BaseModel):
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    mrp = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, null=True, blank=True
    )
    unit = models.CharField(
        choices=Item.ItemUnitType.choices, default=Item.ItemUnitType.NONE, blank=True, null=True
    )
    price = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )
    price_type = models.CharField(
        max_length=20,
        choices=Item.PriceType.choices,
        default=Item.PriceType.WITHOUT_TAX,
        blank=True,
        null=True,
    )
    discount_percentage = models.CharField(max_length=10, blank=True, null=True)
    discount_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )
    tax_type = models.JSONField(blank=True, null=True)
    tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, null=True, blank=True
    )

    def __str__(self):
        return f"{self.item.name} on Bill #{self.bill.bill_id}"


class Transaction(BaseModel):

    class TransactionTypeChoices(models.TextChoices):
        SALE = "SALE", "Sale"
        LITE_SALE = "LITE_SALE", "Lite Sale"
        SALE_E_INVOICE = "SALE_E_INVOICE", "Sale E-Invoice"
        PURCHASE = "PURCHASE", "Purchase"
        PURCHASE_E_INVOICE = "PURCHASE_E_INVOICE", "Purchase E-Invoice"
        CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
        DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"
        SALE_ORDER = "SALE_ORDER", "Sale Order"
        PURCHASE_ORDER = "PURCHASE_ORDER", "Purchase Order"
        PAYMENT_IN = "PAYMENT_IN", "Payment In"
        PAYMENT_OUT = "PAYMENT_OUT", "Payment Out"

    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    transaction_type = models.CharField(
        max_length=50, choices=TransactionTypeChoices.choices, null=True, blank=True
    )
    recipet_no = models.CharField(max_length=50)
    date = models.DateField()
    payment_type = models.JSONField(blank=True, null=True)
    recieved_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    attachment = models.FileField(upload_to="transaction/documents/", blank=True, null=True)


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
