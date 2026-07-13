from decimal import Decimal

from django.db import transaction

from .models import (
    Account,
    ContraVoucher,
    CreditNote,
    DebitNote,
    JournalVoucher,
    Ledger,
    PaymentVoucher,
    PurchaseBill,
    ReceiptVoucher,
    SalesInvoice,
)


def _get_or_create_control_account(name: str, account_type: str) -> Account:
    account, _ = Account.objects.get_or_create(
        name=name, defaults={"account_type": account_type, "is_default": True}
    )
    return account


def _compute_gst(items, state_of_supply, party_state):
    taxable = Decimal("0.00")
    total_gst = Decimal("0.00")
    cgst = Decimal("0.00")
    sgst = Decimal("0.00")
    igst = Decimal("0.00")

    for item in items:
        rate = item.get("gst_value") or getattr(item.item, "gst_value", Decimal("0.00"))
        amt = item.amount or Decimal("0.00")
        taxable += amt
        gst_amt = amt * rate / Decimal("100.00")
        total_gst += gst_amt
        if state_of_supply and party_state and state_of_supply == party_state:
            half = gst_amt / Decimal("2.00")
            cgst += half
            sgst += half
        else:
            igst += gst_amt

    return taxable, total_gst, cgst, sgst, igst


@transaction.atomic
def post_sales_invoice(invoice: SalesInvoice):
    if not invoice.party or not invoice.party.account:
        return

    sales_account = _get_or_create_control_account("Sales", Account.AccountType.REVENUE)
    cgst_account = _get_or_create_control_account("CGST Output", Account.AccountType.LIABILITY)
    sgst_account = _get_or_create_control_account("SGST Output", Account.AccountType.LIABILITY)
    igst_account = _get_or_create_control_account("IGST Output", Account.AccountType.LIABILITY)

    items_data = invoice.items.all()
    taxable_amount, total_gst, cgst, sgst, igst = _compute_gst(
        items_data, invoice.state_of_supply, invoice.party.state if invoice.party else None
    )

    Ledger.objects.create(
        voucher=invoice,
        account=invoice.party.account,
        debit=invoice.total_amount,
        credit=0,
        date=invoice.date,
    )
    Ledger.objects.create(
        voucher=invoice,
        account=sales_account,
        debit=0,
        credit=taxable_amount,
        date=invoice.date,
    )
    if cgst > 0:
        Ledger.objects.create(
            voucher=invoice, account=cgst_account, debit=0, credit=cgst, date=invoice.date
        )
        Ledger.objects.create(
            voucher=invoice, account=sgst_account, debit=0, credit=sgst, date=invoice.date
        )
    if igst > 0:
        Ledger.objects.create(
            voucher=invoice, account=igst_account, debit=0, credit=igst, date=invoice.date
        )


@transaction.atomic
def post_purchase_bill(purchase_bill: PurchaseBill):
    if not purchase_bill.party or not purchase_bill.party.account:
        return

    purchase_account = _get_or_create_control_account("Purchases", Account.AccountType.EXPENSE)
    cgst_input = _get_or_create_control_account("CGST Input", Account.AccountType.ASSET)
    sgst_input = _get_or_create_control_account("SGST Input", Account.AccountType.ASSET)
    igst_input = _get_or_create_control_account("IGST Input", Account.AccountType.ASSET)

    items_data = purchase_bill.items.all()
    taxable_amount, total_gst, cgst, sgst, igst = _compute_gst(
        items_data,
        purchase_bill.state_of_supply,
        purchase_bill.party.state if purchase_bill.party else None,
    )

    Ledger.objects.create(
        voucher=purchase_bill,
        account=purchase_bill.party.account,
        debit=0,
        credit=purchase_bill.total_amount,
        date=purchase_bill.date,
    )
    Ledger.objects.create(
        voucher=purchase_bill,
        account=purchase_account,
        debit=taxable_amount,
        credit=0,
        date=purchase_bill.date,
    )
    if cgst > 0:
        Ledger.objects.create(
            voucher=purchase_bill,
            account=cgst_input,
            debit=cgst,
            credit=0,
            date=purchase_bill.date,
        )
        Ledger.objects.create(
            voucher=purchase_bill,
            account=sgst_input,
            debit=sgst,
            credit=0,
            date=purchase_bill.date,
        )
    if igst > 0:
        Ledger.objects.create(
            voucher=purchase_bill,
            account=igst_input,
            debit=igst,
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
def post_contra_voucher(contra: ContraVoucher):
    """Posts a contra voucher to the ledger."""
    Ledger.objects.create(
        voucher=contra,
        account=contra.from_account,
        debit=contra.amount,
        credit=0,
        date=contra.date,
    )
    Ledger.objects.create(
        voucher=contra,
        account=contra.to_account,
        debit=0,
        credit=contra.amount,
        date=contra.date,
    )


@transaction.atomic
def post_credit_note(credit_note: CreditNote):
    """Posts a credit note (reverse of sales invoice)."""
    if not credit_note.party or not credit_note.party.account:
        return

    sales_return_account = _get_or_create_control_account(
        "Sales Returns", Account.AccountType.REVENUE
    )
    cgst_account = _get_or_create_control_account("CGST Output", Account.AccountType.LIABILITY)
    sgst_account = _get_or_create_control_account("SGST Output", Account.AccountType.LIABILITY)
    igst_account = _get_or_create_control_account("IGST Output", Account.AccountType.LIABILITY)

    # Credit the party (reduce their receivable)
    Ledger.objects.create(
        voucher=credit_note,
        account=credit_note.party.account,
        debit=0,
        credit=credit_note.total_amount,
        date=credit_note.date,
    )
    # Debit sales return
    items_data = credit_note.items.all()
    taxable_amount, total_gst, cgst, sgst, igst = _compute_gst(
        items_data,
        credit_note.state_of_supply,
        credit_note.party.state if credit_note.party else None,
    )
    Ledger.objects.create(
        voucher=credit_note,
        account=sales_return_account,
        debit=taxable_amount,
        credit=0,
        date=credit_note.date,
    )
    if cgst > 0:
        Ledger.objects.create(
            voucher=credit_note, account=cgst_account, debit=cgst, credit=0, date=credit_note.date
        )
        Ledger.objects.create(
            voucher=credit_note, account=sgst_account, debit=sgst, credit=0, date=credit_note.date
        )
    if igst > 0:
        Ledger.objects.create(
            voucher=credit_note, account=igst_account, debit=igst, credit=0, date=credit_note.date
        )


@transaction.atomic
def post_debit_note(debit_note: DebitNote):
    """Posts a debit note (reverse of purchase bill)."""
    if not debit_note.party or not debit_note.party.account:
        return

    purchase_return_account = _get_or_create_control_account(
        "Purchase Returns", Account.AccountType.EXPENSE
    )
    cgst_input = _get_or_create_control_account("CGST Input", Account.AccountType.ASSET)
    sgst_input = _get_or_create_control_account("SGST Input", Account.AccountType.ASSET)
    igst_input = _get_or_create_control_account("IGST Input", Account.AccountType.ASSET)

    # Debit the party (reduce their payable)
    Ledger.objects.create(
        voucher=debit_note,
        account=debit_note.party.account,
        debit=debit_note.total_amount,
        credit=0,
        date=debit_note.date,
    )
    # Credit purchase return
    items_data = debit_note.items.all()
    taxable_amount, total_gst, cgst, sgst, igst = _compute_gst(
        items_data,
        debit_note.state_of_supply,
        debit_note.party.state if debit_note.party else None,
    )
    Ledger.objects.create(
        voucher=debit_note,
        account=purchase_return_account,
        debit=0,
        credit=taxable_amount,
        date=debit_note.date,
    )
    if cgst > 0:
        Ledger.objects.create(
            voucher=debit_note, account=cgst_input, debit=cgst, credit=0, date=debit_note.date
        )
        Ledger.objects.create(
            voucher=debit_note, account=sgst_input, debit=sgst, credit=0, date=debit_note.date
        )
    if igst > 0:
        Ledger.objects.create(
            voucher=debit_note, account=igst_input, debit=igst, credit=0, date=debit_note.date
        )


@transaction.atomic
def post_voucher(voucher):
    """Generic posting function that dispatches to the correct service."""
    if voucher.is_posted:
        return

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
    elif isinstance(voucher, ContraVoucher):
        post_contra_voucher(voucher)
    elif isinstance(voucher, CreditNote):
        post_credit_note(voucher)
    elif isinstance(voucher, DebitNote):
        post_debit_note(voucher)
    else:
        raise TypeError(f"Unsupported voucher type: {type(voucher).__name__}")

    voucher.is_posted = True
    voucher.save(update_fields=["is_posted"])
