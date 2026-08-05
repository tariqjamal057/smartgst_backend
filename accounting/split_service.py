"""Split Company — create a next-financial-year company from the current one.

The new tenant receives a fresh company id, a copy of the master data
(accounts, parties, items, categories, invoice settings) and a posted
"Opening Balance" journal that carries forward account balances from the
source ledger, plus the current closing stock on items.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from tenants.models import Tenant, TenantUser

from .models import (
    Account,
    CompanySetting,
    FinancialYear,
    InvoiceSetting,
    Item,
    ItemCategory,
    JournalVoucher,
    JournalVoucherEntry,
    Ledger,
    Party,
    PurchaseBillItem,
    SalesInvoiceItem,
    generate_company_id,
)
from .services import post_voucher


def _add_years(date_obj, years):
    try:
        return date_obj.replace(year=date_obj.year + years)
    except ValueError:
        return date_obj.replace(year=date_obj.year + years, day=28)


def _copy_fields(source, target, exclude=()):
    for field in source._meta.concrete_fields:
        name = field.name
        if name in exclude or name in ("id", "uuid", "tenant"):
            continue
        setattr(target, name, getattr(source, name))


@transaction.atomic
def split_company(tenant, user, split_date):
    source = CompanySetting.objects.filter(tenant=tenant, is_active=True).first()
    if source is None:
        raise ValueError("No active company found for this tenant.")

    new_company_id = generate_company_id()
    new_tenant = Tenant.objects.create(
        name=f"{source.company_name} ({new_company_id})",
        subdomain_name=new_company_id,
        gstin=source.gstin or "",
        pan=getattr(source, "pan", "") or "",
        state=source.state or "",
        email=source.email or "",
        registration_type=source.registration_type or "",
    )
    TenantUser.objects.create(tenant=new_tenant, user=user, role="ADMIN")

    company = CompanySetting(tenant=new_tenant, company_id=new_company_id, created_by=user)
    _copy_fields(
        source,
        company,
        exclude=("company_id", "created_by", "financial_year", "book_beginning"),
    )
    company.financial_year = f"{split_date.year}-{str(split_date.year + 1)[-2:]}"
    company.book_beginning = split_date
    company.save()

    fy_end = _add_years(split_date, 1) - timedelta(days=1)
    financial_year = FinancialYear.objects.create(
        tenant=new_tenant,
        start_date=split_date,
        end_date=fy_end,
        is_locked=False,
    )

    old_accounts = {a.id: a for a in Account.objects.filter(tenant_id=tenant.id)}
    old_items = list(Item.objects.filter(tenant_id=tenant.id))

    # Copy item categories, then items with the closing stock carried forward.
    new_categories = {}
    for category in ItemCategory.objects.filter(tenant_id=tenant.id):
        new_cat = ItemCategory(tenant=new_tenant)
        _copy_fields(category, new_cat)
        new_cat.save()
        new_categories[category.id] = new_cat

    new_items = {}
    for item in old_items:
        opening = item.opening_quantity or Decimal("0.00")
        purchase_qty = (
            PurchaseBillItem.objects.filter(bill__tenant_id=tenant.id, item=item)
            .exclude(bill__date__gte=split_date)
            .aggregate(q=Sum("quantity"))["q"]
            or 0
        )
        sale_qty = (
            SalesInvoiceItem.objects.filter(invoice__tenant_id=tenant.id, item=item)
            .exclude(invoice__date__gte=split_date)
            .aggregate(q=Sum("quantity"))["q"]
            or 0
        )
        closing_stock = opening + purchase_qty - sale_qty
        new_item = Item(tenant=new_tenant, category=new_categories.get(item.category_id))
        _copy_fields(item, new_item, exclude=("opening_quantity", "as_of_date"))
        new_item.opening_quantity = closing_stock
        new_item.as_of_date = split_date
        new_item.save()
        new_items[item.id] = new_item

    # Copy accounts (parent links wired in a second pass).
    new_accounts = {}
    for account_id, account in old_accounts.items():
        new_account = Account(tenant=new_tenant)
        _copy_fields(account, new_account, exclude=("parent",))
        new_account.save()
        new_accounts[account_id] = new_account
    for account_id, account in old_accounts.items():
        if account.parent_id and account.parent_id in new_accounts:
            new_accounts[account_id].parent = new_accounts[account.parent_id]
            new_accounts[account_id].save(update_fields=["parent"])

    # Copy parties, remapping their linked accounts.
    for party in Party.objects.filter(tenant_id=tenant.id):
        new_party = Party(
            tenant=new_tenant,
            account=new_accounts.get(party.account_id),
        )
        _copy_fields(party, new_party, exclude=("account",))
        new_party.save()

    # Copy invoice number settings.
    for setting in InvoiceSetting.objects.filter(tenant_id=tenant.id):
        new_setting = InvoiceSetting(tenant=new_tenant)
        _copy_fields(setting, new_setting)
        new_setting.save()

    _create_opening_balance(tenant.id, new_tenant, new_accounts, financial_year, split_date)

    return {
        "company_id": new_company_id,
        "company_name": source.company_name,
        "tenant_id": new_tenant.id,
        "financial_year": company.financial_year,
    }


def _create_opening_balance(old_tenant_id, new_tenant, new_accounts, financial_year, split_date):
    balances = {}
    for row in (
        Ledger.objects.filter(account__tenant_id=old_tenant_id, date__lt=split_date)
        .values("account_id")
        .annotate(total=Sum("debit") - Sum("credit"))
    ):
        net = row["total"] or Decimal("0.00")
        if net != 0:
            balances[row["account_id"]] = net

    if not balances:
        return

    voucher = JournalVoucher.objects.create(
        tenant=new_tenant,
        financial_year=financial_year,
        voucher_number="OPENING",
        date=split_date,
        narration="Opening balances carried forward on company split",
    )

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for old_account_id, net in balances.items():
        new_account = new_accounts.get(old_account_id)
        if new_account is None:
            continue
        if net > 0:
            JournalVoucherEntry.objects.create(
                voucher=voucher, account=new_account, debit=net, credit=0
            )
            total_debit += net
        else:
            JournalVoucherEntry.objects.create(
                voucher=voucher, account=new_account, debit=0, credit=abs(net)
            )
            total_credit += abs(net)

    if total_debit != total_credit:
        opening_account = Account.objects.create(
            tenant=new_tenant,
            name="Opening Balance",
            account_type=Account.AccountType.EQUITY,
            is_default=False,
        )
        difference = total_debit - total_credit
        if difference > 0:
            JournalVoucherEntry.objects.create(
                voucher=voucher, account=opening_account, debit=0, credit=difference
            )
        else:
            JournalVoucherEntry.objects.create(
                voucher=voucher, account=opening_account, debit=abs(difference), credit=0
            )

    post_voucher(voucher)
