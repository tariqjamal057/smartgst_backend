from django.db import transaction

from .models import (
    Account,
    JournalVoucher,
    Ledger,
    PaymentVoucher,
    PurchaseBill,
    ReceiptVoucher,
    SalesInvoice,
)


def _get_or_create_control_account(name: str, account_type: str) -> Account:
    """Helper to get or create a default control account."""
    account, _ = Account.objects.get_or_create(
        name=name, defaults={"account_type": account_type, "is_default": True}
    )
    return account


@transaction.atomic
def post_sales_invoice(invoice: SalesInvoice):
    """
    Posts a sales invoice to the ledger.

    Debit: Customer's Account
    Credit: Sales Account
    Credit: GST Account(s)
    """
    sales_account = _get_or_create_control_account("Sales", Account.AccountType.REVENUE)
    gst_output_account = _get_or_create_control_account(
        "GST Output", Account.AccountType.LIABILITY
    )

    # For simplicity, we assume total_amount includes tax.
    # A more detailed implementation would calculate tax from items.
    taxable_amount = invoice.total_amount / 1.18  # Assuming a flat 18% GST rate
    gst_amount = invoice.total_amount - taxable_amount

    # Debit the customer
    Ledger.objects.create(
        voucher=invoice,
        account=invoice.customer.account,
        debit=invoice.total_amount,
        credit=0,
        date=invoice.date,
    )
    # Credit Sales
    Ledger.objects.create(
        voucher=invoice,
        account=sales_account,
        debit=0,
        credit=taxable_amount,
        date=invoice.date,
    )
    # Credit GST Output
    Ledger.objects.create(
        voucher=invoice,
        account=gst_output_account,
        debit=0,
        credit=gst_amount,
        date=invoice.date,
    )


@transaction.atomic
def post_purchase_bill(purchase_bill: PurchaseBill):
    """
    Posts a purchase bill to the ledger.

    Debit: Purchase Account
    Debit: GST Account(s)
    Credit: Vendor's Account
    """
    purchase_account = _get_or_create_control_account("Purchases", Account.AccountType.EXPENSE)
    gst_input_account = _get_or_create_control_account("GST Input", Account.AccountType.ASSET)

    taxable_amount = purchase_bill.total_amount / 1.18  # Assuming a flat 18% GST rate
    gst_amount = purchase_bill.total_amount - taxable_amount

    # Credit the vendor
    Ledger.objects.create(
        voucher=purchase_bill,
        account=purchase_bill.vendor.account,
        debit=0,
        credit=purchase_bill.total_amount,
        date=purchase_bill.date,
    )
    # Debit Purchases
    Ledger.objects.create(
        voucher=purchase_bill,
        account=purchase_account,
        debit=taxable_amount,
        credit=0,
        date=purchase_bill.date,
    )
    # Debit GST Input
    Ledger.objects.create(
        voucher=purchase_bill,
        account=gst_input_account,
        debit=gst_amount,
        credit=0,
        date=purchase_bill.date,
    )


@transaction.atomic
def post_receipt_voucher(receipt_voucher: ReceiptVoucher):
    """
    Posts a receipt voucher to the ledger.

    Debit: Cash/Bank Account
    Credit: Party's Account
    """
    # Debit the bank/cash account
    Ledger.objects.create(
        voucher=receipt_voucher,
        account=receipt_voucher.received_in,
        debit=receipt_voucher.amount,
        credit=0,
        date=receipt_voucher.date,
    )
    # Credit the party's account
    Ledger.objects.create(
        voucher=receipt_voucher,
        account=receipt_voucher.party.account,
        debit=0,
        credit=receipt_voucher.amount,
        date=receipt_voucher.date,
    )


@transaction.atomic
def post_payment_voucher(payment_voucher: PaymentVoucher):
    """
    Posts a payment voucher to the ledger.

    Debit: Party's Account
    Credit: Cash/Bank Account
    """
    # Debit the party's account
    Ledger.objects.create(
        voucher=payment_voucher,
        account=payment_voucher.party.account,
        debit=payment_voucher.amount,
        credit=0,
        date=payment_voucher.date,
    )
    # Credit the bank/cash account
    Ledger.objects.create(
        voucher=payment_voucher,
        account=payment_voucher.paid_from,
        debit=0,
        credit=payment_voucher.amount,
        date=payment_voucher.date,
    )


@transaction.atomic
def post_journal_voucher(journal_voucher: JournalVoucher):
    """Posts a journal voucher to the ledger from its entries."""
    for entry in journal_voucher.entries.all():
        Ledger.objects.create(
            voucher=journal_voucher,
            account=entry.account,
            debit=entry.debit,
            credit=entry.credit,
            date=journal_voucher.date,
        )


@transaction.atomic
def post_voucher(voucher):
    """
    Generic posting function that dispatches to the correct service.

    based on the voucher type.
    """
    if voucher.is_posted:
        return  # Do not post a voucher twice

    if isinstance(voucher, SalesInvoice):
        post_sales_invoice(voucher)
    elif isinstance(voucher, PurchaseBill):
        post_purchase_bill(voucher)
    elif isinstance(voucher, ReceiptVoucher):
        post_receipt_voucher(voucher)
    elif isinstance(voucher, PaymentVoucher):
        post_payment_voucher(voucher)
    elif isinstance(voucher, JournalVoucher):
        post_journal_voucher(voucher)
    else:
        raise TypeError(f"Unsupported voucher type: {type(voucher).__name__}")

    voucher.is_posted = True
    voucher.save(update_fields=["is_posted"])
