import secrets
import string

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseModel, TenantAwareModel


def generate_company_id():
    while True:
        cid = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        if not CompanySetting.objects.filter(company_id=cid).exists():
            return cid


class CompanySetting(TenantAwareModel):
    company_id = models.CharField(max_length=6, unique=True, default=generate_company_id)
    company_name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    branch_address = models.TextField(blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    financial_year = models.CharField(max_length=20, blank=True)
    book_beginning = models.DateField(null=True, blank=True)
    return_type = models.CharField(max_length=20, blank=True, default="Monthly")
    registration_type = models.CharField(max_length=50, blank=True)
    use_inventory = models.CharField(max_length=10, blank=True, default="No")
    eway_bill = models.CharField(max_length=10, blank=True, default="No")
    eway_bill_threshold = models.CharField(max_length=20, blank=True, default="50000")
    ewb_login_id = models.CharField(max_length=100, blank=True)
    ewb_password = models.CharField(max_length=100, blank=True)
    e_invoice = models.CharField(max_length=10, blank=True, default="No")
    einvoice_login_id = models.CharField(max_length=100, blank=True)
    einvoice_password = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_companies",
    )

    class Meta:
        verbose_name_plural = "Company Settings"

    def __str__(self):
        return self.company_name


class InvoiceSetting(TenantAwareModel):
    class VoucherType(models.TextChoices):
        SALES = "SALES", "Sales"
        PURCHASE = "PURCHASE", "Purchase"
        PAYMENT = "PAYMENT", "Payment"
        RECEIPT = "RECEIPT", "Receipt"
        JOURNAL = "JOURNAL", "Journal"
        CONTRA = "CONTRA", "Contra"
        CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
        DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"
        DELIVERY_CHALLAN = "DELIVERY_CHALLAN", "Delivery Challan"
        SALE_ORDER = "SALE_ORDER", "Sale Order"
        PURCHASE_ORDER = "PURCHASE_ORDER", "Purchase Order"

    voucher_type = models.CharField(max_length=30, choices=VoucherType.choices, unique=True)
    prefix = models.CharField(max_length=20, blank=True, default="")
    suffix = models.CharField(max_length=20, blank=True, default="")
    zero_padding = models.PositiveIntegerField(default=4)
    next_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [["tenant", "voucher_type"]]

    def __str__(self):
        number = f"{self.next_number:0{self.zero_padding}d}"
        return f"{self.voucher_type} - {self.prefix}{number}{self.suffix}"


class InvoicePreferences(TenantAwareModel):
    default_settings = models.JSONField(default=dict, blank=True)
    printing_settings = models.JSONField(default=dict, blank=True)
    voucher_config = models.JSONField(default=dict, blank=True)
    ref_config = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Invoice Preferences"
        unique_together = [["tenant"]]

    def __str__(self):
        return f"Invoice Preferences (tenant {self.tenant_id})"


class InvoiceBook(TenantAwareModel):
    name = models.CharField(max_length=100)
    under = models.CharField(max_length=100, blank=True, default="sale")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Invoice Books"
        unique_together = [["tenant", "name"]]

    def __str__(self):
        return self.name


class FinancialYear(TenantAwareModel):
    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Financial Years"
        ordering = ["-start_date"]
        unique_together = [["tenant", "start_date"]]

    def __str__(self):
        return f"{self.start_date} to {self.end_date}"


class Account(TenantAwareModel):
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

    class Meta:
        verbose_name_plural = "Chart of Accounts"
        unique_together = [["tenant", "name"]]

    def __str__(self):
        return self.name


class Party(TenantAwareModel):
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
    custom_fields = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Parties"
        unique_together = [["tenant", "name", "party_type"]]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.account:
            if self.party_type == self.PartyType.CUSTOMER:
                parent_account_name = "Sundry Debtors"
                parent_account_type = Account.AccountType.ASSET
            else:
                parent_account_name = "Sundry Creditors"
                parent_account_type = Account.AccountType.LIABILITY

            tenant_filter = {"tenant": self.tenant} if self.tenant_id else {}
            parent_account, _ = Account.objects.get_or_create(
                name=parent_account_name,
                defaults={
                    "account_type": parent_account_type,
                    "is_default": True,
                    **tenant_filter,
                },
                **tenant_filter,
            )

            existing = (
                Account.objects.filter(name=self.name, **tenant_filter)
                .exclude(party_account__isnull=False)
                .first()
            )
            if existing is not None:
                party_account = existing
            else:
                account_name = self.name
                index = 1
                while Account.objects.filter(name=account_name, **tenant_filter).exists():
                    index += 1
                    account_name = f"{self.name} ({index})"
                party_account = Account.objects.create(
                    name=account_name,
                    account_type=parent_account.account_type,
                    parent=parent_account,
                    tenant=self.tenant,
                )
            self.account = party_account
            self.save(update_fields=["account"])


class ItemCategory(TenantAwareModel):
    name = models.CharField(max_length=100)
    hsn_code = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name_plural = "Item Categories"
        unique_together = [["tenant", "name"]]

    def __str__(self):
        return self.name


class Godown(TenantAwareModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Godowns"
        unique_together = [["tenant", "name"]]

    def __str__(self):
        return self.name


class Item(TenantAwareModel):
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

    name = models.CharField(max_length=100)
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

    class Meta:
        verbose_name_plural = "Items"
        unique_together = [["tenant", "name"]]

    def __str__(self):
        return self.name


class BaseVoucher(TenantAwareModel):
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    voucher_number = models.CharField(max_length=50)
    date = models.DateField()
    narration = models.TextField(blank=True)
    is_posted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True


class BaseOrder(TenantAwareModel):
    class SupplyType(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        SEZ = "SEZ", "SEZ"
        EXPORT = "EXPORT", "Export"

    order_number = models.CharField(max_length=50)
    date = models.DateField()
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    party = models.ForeignKey(Party, on_delete=models.PROTECT, null=True, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    state_of_supply = models.CharField(max_length=50, blank=True)
    supply_type = models.CharField(
        max_length=20, choices=SupplyType.choices, default=SupplyType.REGULAR
    )
    narration = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    round_off = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_converted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class SaleOrder(BaseOrder):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_terms = models.TextField(blank=True)
    delivery_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "order_number"]]

    def __str__(self):
        return f"Sale Order #{self.order_number}"


class SaleOrderItem(BaseModel):
    order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class PurchaseOrder(BaseOrder):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_terms = models.TextField(blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    transporter_name = models.CharField(max_length=100, blank=True)
    vehicle_no = models.CharField(max_length=50, blank=True)
    lr_rr_no = models.CharField(max_length=50, blank=True)
    port_of_export = models.CharField(max_length=100, blank=True)
    shipping_bill_no = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "order_number"]]

    def __str__(self):
        return f"Purchase Order #{self.order_number}"


class PurchaseOrderItem(BaseModel):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class DeliveryChallan(TenantAwareModel):
    class ChallanType(models.TextChoices):
        SALES = "SALES", "Sales"
        PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase Return"
        JOB_WORK = "JOB_WORK", "Job Work"
        FREE = "FREE", "Free"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    challan_number = models.CharField(max_length=50)
    date = models.DateField()
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    challan_type = models.CharField(
        max_length=30, choices=ChallanType.choices, default=ChallanType.SALES
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    party = models.ForeignKey(Party, on_delete=models.PROTECT, null=True, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    state_of_supply = models.CharField(max_length=50, blank=True)
    transporter_name = models.CharField(max_length=100, blank=True)
    vehicle_no = models.CharField(max_length=50, blank=True)
    lr_rr_no = models.CharField(max_length=50, blank=True)
    narration = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_invoiced = models.BooleanField(default=False)
    eway_bill_no = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "challan_number"]]

    def __str__(self):
        return f"DC #{self.challan_number}"


class DeliveryChallanItem(BaseModel):
    challan = models.ForeignKey(DeliveryChallan, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    rate = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class SalesInvoice(BaseVoucher):
    class SupplyType(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        SEZ = "SEZ", "SEZ"
        EXPORT = "EXPORT", "Export"

    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, null=True, blank=True, related_name="sales_invoices"
    )
    bill_id = models.CharField(max_length=50, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)
    state_of_supply = models.CharField(max_length=50, blank=True, null=True)
    supply_type = models.CharField(
        max_length=20, choices=SupplyType.choices, default=SupplyType.REGULAR
    )
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    payment_type = models.JSONField(blank=True, null=True)
    round_off_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_taxable_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="invoice/images/", blank=True, null=True)
    documents = models.FileField(upload_to="invoice/documents/", blank=True, null=True)
    eway_bill_no = models.CharField(max_length=50, blank=True)
    transporter_name = models.CharField(max_length=100, blank=True)
    vehicle_no = models.CharField(max_length=50, blank=True)
    lr_rr_no = models.CharField(max_length=50, blank=True)
    mode_of_transport = models.CharField(max_length=50, blank=True)
    ecommerce_gstin = models.CharField(max_length=15, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Sales Invoice #{self.bill_id}"


class AbstractInvoiceItem(BaseModel):
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True, null=True, default=None)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    price_type = models.CharField(
        max_length=20,
        choices=Item.PriceType.choices,
        default=Item.PriceType.WITHOUT_TAX,
        blank=True,
    )
    mrp = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        abstract = True


class SalesInvoiceItem(AbstractInvoiceItem):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="items")

    def __str__(self):
        return f"{self.item.name} on Invoice #{self.invoice.bill_id}"


class PurchaseBill(BaseVoucher):
    class SupplyType(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        SEZ = "SEZ", "SEZ"
        EXPORT = "EXPORT", "Export"

    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_bills"
    )
    bill_id = models.CharField(max_length=50, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)
    state_of_supply = models.CharField(max_length=50, blank=True, null=True)
    supply_type = models.CharField(
        max_length=20, choices=SupplyType.choices, default=SupplyType.REGULAR
    )
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    payment_type = models.JSONField(blank=True, null=True)
    round_off_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_taxable_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="purchase/images/", blank=True, null=True)
    documents = models.FileField(upload_to="purchase/documents/", blank=True, null=True)
    eway_bill_no = models.CharField(max_length=50, blank=True)
    transporter_name = models.CharField(max_length=100, blank=True)
    vehicle_no = models.CharField(max_length=50, blank=True)
    lr_rr_no = models.CharField(max_length=50, blank=True)
    mode_of_transport = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Purchase Bill #{self.bill_id}"


class PurchaseBillItem(AbstractInvoiceItem):
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name="items")

    def __str__(self):
        return f"{self.item.name} on Bill #{self.bill.bill_id}"


class Transaction(TenantAwareModel):

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
    voucher_type = models.CharField(max_length=50, blank=True)
    transaction_type = models.CharField(
        max_length=50, choices=TransactionTypeChoices.choices, null=True, blank=True
    )
    receipt_no = models.CharField(max_length=50)
    date = models.DateField()
    payment_type = models.JSONField(blank=True, null=True)
    received_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to="transaction/documents/", blank=True, null=True)


class ReceiptVoucher(BaseVoucher):
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    received_in = models.ForeignKey(Account, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Receipt #{self.voucher_number}"


class PaymentVoucher(BaseVoucher):
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    paid_from = models.ForeignKey(Account, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Payment #{self.voucher_number}"


class JournalVoucher(BaseVoucher):
    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Journal #{self.voucher_number}"


class JournalVoucherEntry(BaseModel):
    voucher = models.ForeignKey(JournalVoucher, on_delete=models.CASCADE, related_name="entries")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        verbose_name_plural = "Journal Voucher Entries"


class ContraVoucher(BaseVoucher):
    class ContraType(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
        TRANSFER = "TRANSFER", "Transfer"

    contra_type = models.CharField(max_length=20, choices=ContraType.choices)
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="contra_from")
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="contra_to")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    cheque_no = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Contra #{self.voucher_number}"


class CreditNote(BaseVoucher):
    class NoteType(models.TextChoices):
        SALES_RETURN = "SALES_RETURN", "Sales Return"
        CREDIT = "CREDIT", "Credit"

    note_type = models.CharField(
        max_length=20, choices=NoteType.choices, default=NoteType.SALES_RETURN
    )
    party = models.ForeignKey(Party, on_delete=models.PROTECT, null=True, blank=True)
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.SET_NULL, null=True, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    state_of_supply = models.CharField(max_length=50, blank=True)
    supply_type = models.CharField(
        max_length=20, choices=BaseOrder.SupplyType.choices, default=BaseOrder.SupplyType.REGULAR
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    round_off = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    eway_bill_no = models.CharField(max_length=50, blank=True)
    transporter_name = models.CharField(max_length=100, blank=True)
    vehicle_no = models.CharField(max_length=50, blank=True)
    lr_rr_no = models.CharField(max_length=50, blank=True)
    mode_of_transport = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Credit Note #{self.voucher_number}"


class CreditNoteItem(BaseModel):
    credit_note = models.ForeignKey(CreditNote, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class DebitNote(BaseVoucher):
    class NoteType(models.TextChoices):
        PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase Return"
        DEBIT = "DEBIT", "Debit"

    note_type = models.CharField(
        max_length=20, choices=NoteType.choices, default=NoteType.PURCHASE_RETURN
    )
    party = models.ForeignKey(Party, on_delete=models.PROTECT, null=True, blank=True)
    bill = models.ForeignKey(PurchaseBill, on_delete=models.SET_NULL, null=True, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    state_of_supply = models.CharField(max_length=50, blank=True)
    supply_type = models.CharField(
        max_length=20, choices=BaseOrder.SupplyType.choices, default=BaseOrder.SupplyType.REGULAR
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    round_off = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    eway_bill_no = models.CharField(max_length=50, blank=True)
    transporter_name = models.CharField(max_length=100, blank=True)
    vehicle_no = models.CharField(max_length=50, blank=True)
    lr_rr_no = models.CharField(max_length=50, blank=True)
    mode_of_transport = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [["tenant", "financial_year", "voucher_number"]]

    def __str__(self):
        return f"Debit Note #{self.voucher_number}"


class DebitNoteItem(BaseModel):
    debit_note = models.ForeignKey(DebitNote, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class Document(TenantAwareModel):
    class DocCategory(models.TextChoices):
        INVOICE = "INVOICE", "Invoice"
        RECEIPT = "RECEIPT", "Receipt"
        PAYMENT = "PAYMENT", "Payment"
        ORDER = "ORDER", "Order"
        CHALLAN = "CHALLAN", "Challan"
        OTHERS = "OTHERS", "Others"

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=DocCategory.choices)
    file = models.FileField(upload_to="documents/")
    party = models.ForeignKey(Party, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title


class Ledger(BaseModel):
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
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]


class SaleReturn(TenantAwareModel):
    return_number = models.CharField(max_length=50)
    date = models.DateField()
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="returns")
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_settled = models.BooleanField(default=False)

    class Meta:
        unique_together = [["tenant", "financial_year", "return_number"]]

    def __str__(self):
        return f"Sale Return #{self.return_number}"


class SaleReturnItem(BaseModel):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class PurchaseReturn(TenantAwareModel):
    return_number = models.CharField(max_length=50)
    date = models.DateField()
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name="returns")
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_settled = models.BooleanField(default=False)

    class Meta:
        unique_together = [["tenant", "financial_year", "return_number"]]

    def __str__(self):
        return f"Purchase Return #{self.return_number}"


class PurchaseReturnItem(BaseModel):
    purchase_return = models.ForeignKey(
        PurchaseReturn, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)


class BankReconciliation(TenantAwareModel):
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="reconciliations")
    statement_date = models.DateField()
    statement_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    system_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    difference = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-statement_date"]

    def __str__(self):
        return f"Recon {self.account.name} @ {self.statement_date}"
