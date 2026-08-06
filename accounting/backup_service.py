"""
Backup and restore of tenant-scoped accounting data as JSON.

Backup exports every accounting model owned by a tenant (including child
rows such as invoice items) in dependency order. Restore re-creates the
rows, remapping old primary keys to new ones so foreign keys stay intact.
"""

import json
from datetime import date, datetime
from decimal import Decimal

from django.db import models, transaction

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
    Godown,
    InvoiceBook,
    InvoicePreferences,
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

# (label, model, parent_field) — parent_field is used to scope child models
# that have no `tenant` column to a tenant through their parent row.
BACKUP_MODELS = [
    ("financial_years", FinancialYear, None),
    ("accounts", Account, None),
    ("item_categories", ItemCategory, None),
    ("godowns", Godown, None),
    ("items", Item, None),
    ("parties", Party, None),
    ("invoice_settings", InvoiceSetting, None),
    ("invoice_preferences", InvoicePreferences, None),
    ("invoice_books", InvoiceBook, None),
    ("sale_orders", SaleOrder, None),
    ("sale_order_items", SaleOrderItem, "order"),
    ("purchase_orders", PurchaseOrder, None),
    ("purchase_order_items", PurchaseOrderItem, "order"),
    ("delivery_challans", DeliveryChallan, None),
    ("delivery_challan_items", DeliveryChallanItem, "challan"),
    ("sales_invoices", SalesInvoice, None),
    ("sales_invoice_items", SalesInvoiceItem, "invoice"),
    ("purchase_bills", PurchaseBill, None),
    ("purchase_bill_items", PurchaseBillItem, "bill"),
    ("transactions", Transaction, None),
    ("receipt_vouchers", ReceiptVoucher, None),
    ("payment_vouchers", PaymentVoucher, None),
    ("journal_vouchers", JournalVoucher, None),
    ("journal_entries", JournalVoucherEntry, "voucher"),
    ("contra_vouchers", ContraVoucher, None),
    ("credit_notes", CreditNote, None),
    ("credit_note_items", CreditNoteItem, "credit_note"),
    ("debit_notes", DebitNote, None),
    ("debit_note_items", DebitNoteItem, "debit_note"),
    ("sale_returns", SaleReturn, None),
    ("sale_return_items", SaleReturnItem, "sale_return"),
    ("purchase_returns", PurchaseReturn, None),
    ("purchase_return_items", PurchaseReturnItem, "purchase_return"),
    ("bank_reconciliations", BankReconciliation, None),
    ("documents", Document, None),
]


def _tenant_queryset(model, tenant_id, parent_field=None):
    if parent_field:
        return model.objects.filter(**{f"{parent_field}__tenant_id": tenant_id})
    return model.objects.filter(tenant_id=tenant_id)


def _serialize_instance(obj):
    data = {}
    for field in obj._meta.concrete_fields:
        if field.name == "tenant":
            continue
        if isinstance(field, (models.FileField, models.ImageField)):
            data[field.name] = str(getattr(obj, field.name) or "")
            continue
        value = getattr(obj, field.attname)
        if value is None:
            data[field.name] = None
        elif isinstance(value, Decimal):
            data[field.name] = str(value)
        elif isinstance(value, (date, datetime)):
            data[field.name] = value.isoformat()
        else:
            data[field.name] = value
    return data


def export_tenant_data(tenant_id):
    data = {
        "schema_version": 1,
        "tenant_id": tenant_id,
    }
    for label, model, parent_field in BACKUP_MODELS:
        rows = _tenant_queryset(model, tenant_id, parent_field)
        data[label] = [_serialize_instance(obj) for obj in rows.iterator()]
    return data


def export_tenant_json(tenant_id):
    return json.dumps(export_tenant_data(tenant_id), default=str, indent=2)


MODEL_LABELS = {model.__name__.lower(): label for label, model, _ in BACKUP_MODELS}


@transaction.atomic
def restore_tenant_json(tenant, payload):
    """Re-create all tenant data from a parsed backup dict.

    Existing data for the tenant is removed first, then rows are re-created
    in dependency order with foreign keys remapped to the new primary keys.
    """
    if not isinstance(payload, dict) or "schema_version" not in payload:
        raise ValueError("Invalid backup file.")

    _delete_tenant_data(tenant.id)
    pk_map = {}  # (label, old_pk) -> new object

    # Pass 1: create rows without self-referencing FKs (Account.parent).
    for label, model, parent_field in BACKUP_MODELS:
        rows = payload.get(label, [])
        for row in rows:
            obj = _create_row(model, row, tenant, pk_map, skip_fields={"parent"})
            pk_map[(label, row["id"])] = obj

    # Pass 2: wire self-referencing parent FKs (Account.parent).
    for label, model, parent_field in BACKUP_MODELS:
        if model is not Account:
            continue
        for row in payload.get(label, []):
            obj = pk_map.get((label, row["id"]))
            if obj is None:
                continue
            old_parent = row.get("parent")
            if old_parent:
                parent = pk_map.get((label, old_parent))
                if parent is not None:
                    obj.parent = parent
                    obj.save(update_fields=["parent"])

    return sum(len(payload.get(label, [])) for label, _, _ in BACKUP_MODELS)


def _create_row(model, row, tenant, pk_map, skip_fields=None):
    skip_fields = skip_fields or set()
    kwargs = {"tenant": tenant}
    if hasattr(model, "tenant") is False:
        kwargs.pop("tenant", None)

    for field in model._meta.concrete_fields:
        name = field.name
        if (
            name == model._meta.pk.name
            or name == "uuid"
            or name in skip_fields
            or name == "tenant"
        ):
            continue
        if name not in row:
            continue
        value = row[name]
        if isinstance(field, (models.FileField, models.ImageField)):
            kwargs[name] = value or None
            continue
        if isinstance(field, models.ForeignKey):
            target_label = MODEL_LABELS.get(field.related_model.__name__.lower())
            if value is not None and target_label and (target_label, value) in pk_map:
                kwargs[name] = pk_map[(target_label, value)]
            elif field.null:
                kwargs[name] = None
            continue
        kwargs[name] = value
    return model.objects.create(**kwargs)


def _delete_tenant_data(tenant_id):
    for label, model, parent_field in reversed(BACKUP_MODELS):
        _tenant_queryset(model, tenant_id, parent_field).delete()
