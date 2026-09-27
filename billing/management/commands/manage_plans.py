from django.core.management.base import BaseCommand
from django.db.models import Max, ProtectedError

from billing.models import Plan

PREDEFINED_PLANS = [
    {
        "name": "Starter",
        "price": "9999",
        "period": "year",
        "clients": "10",
        "users": "2",
        "support": "Email",
        "sort_order": 1,
    },
    {
        "name": "Professional",
        "price": "24999",
        "period": "year",
        "clients": "50",
        "users": "12",
        "support": "Priority",
        "sort_order": 2,
    },
    {
        "name": "Enterprise",
        "price": "59999",
        "period": "year",
        "clients": "Unlimited",
        "users": "12",
        "support": "Dedicated",
        "sort_order": 3,
    },
]


def prompt(cls, message, default=None, convert=str, validator=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{message}{suffix}: ").strip()
        if not raw and default is not None:
            raw = str(default)
        if not raw:
            continue
        try:
            value = convert(raw)
        except ValueError:
            cls.stdout.write(cls.style.ERROR(f"  Invalid input: '{raw}'"))
            continue
        if validator and not validator(value):
            cls.stdout.write(cls.style.ERROR("  Value out of allowed range."))
            continue
        return value


class Command(BaseCommand):
    help = "Manage subscription plans: add predefined, add dynamic, list, or delete."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Subscription Plan Manager"))
        self.stdout.write("  1. Add predefined plans (Starter / Professional / Enterprise)")
        self.stdout.write("  2. Add dynamic plans (enter count, then each plan one by one)")
        self.stdout.write("  3. List all plans")
        self.stdout.write("  4. Delete a plan")
        choice = prompt(
            self,
            "Choose an option (1/2/3/4)",
            default="1",
            convert=int,
            validator=lambda v: v in (1, 2, 3, 4),
        )

        if choice == 1:
            self._predefined()
        elif choice == 2:
            self._dynamic()
        elif choice == 3:
            self._list()
        else:
            self._delete()

    def _predefined(self):
        for data in PREDEFINED_PLANS:
            obj, created = Plan.objects.update_or_create(
                name=data["name"],
                defaults={
                    **data,
                    "period": "year",
                    "custom_days": None,
                    "currency": "INR",
                    "is_active": True,
                },
            )
            self.stdout.write(
                self.style.SUCCESS(("Created " if created else "Updated ") + data["name"])
            )

    def _prompt_plan(self, extra_default=None, is_active=True):
        next_order = (Plan.objects.aggregate(m=Max("sort_order"))["m"] or 0) + 1
        name = prompt(self, "  Plan name", default=extra_default)
        price = prompt(
            self,
            "  Price (per period)",
            convert=str,
            validator=lambda v: float(v) >= 0,
        )
        period = prompt(
            self,
            "  Period [year / month / custom]",
            default="year",
            convert=str.lower,
            validator=lambda v: v in ("year", "month", "custom"),
        )
        custom_days = None
        if period == "custom":
            custom_days = prompt(
                self,
                "  Custom days (min 1, max 30)",
                convert=int,
                validator=lambda v: 1 <= v <= 30,
            )
        currency = prompt(self, "  Currency", default="INR").upper()
        clients = prompt(self, "  Clients limit (number or Unlimited)", default="10")
        users = prompt(self, "  Users limit (number or Unlimited)", default="1")
        support = prompt(self, "  Support [Email / Priority / Dedicated]", default="Email")
        return {
            "name": name,
            "price": price,
            "period": period,
            "custom_days": custom_days,
            "currency": currency,
            "clients": clients,
            "users": users,
            "support": support,
            "sort_order": next_order,
            "is_active": is_active,
        }

    def _dynamic(self):
        count = prompt(
            self, "How many plans to add?", default="1", convert=int, validator=lambda v: v >= 1
        )
        created = 0
        for i in range(1, count + 1):
            self.stdout.write(self.style.WARNING(f"\n--- Plan {i} of {count} ---"))
            data = self._prompt_plan()
            _, was_created = Plan.objects.update_or_create(name=data["name"], defaults=data)
            created += 1
            self.stdout.write(self.style.SUCCESS(("+ " if was_created else "~ ") + data["name"]))
        self.stdout.write(self.style.SUCCESS(f"\nDone. {created} plan(s) processed."))

    def _list(self):
        plans = Plan.objects.order_by("sort_order")
        if not plans.exists():
            self.stdout.write(self.style.WARNING("No plans found."))
            return
        for p in plans:
            period = p.period
            if p.period == "custom":
                period = f"{p.custom_days} days"
            self.stdout.write(
                f"{p.id:>3}  {p.name:<14} ₹{p.price:<8}{period:<12} "
                f"clients={p.clients:<10} users={p.users:<4} {'' if p.is_active else '(inactive)'}"
            )

    def _delete(self):
        self._list()
        if not Plan.objects.exists():
            return
        plan_id = prompt(
            self, "Enter the ID of the plan to delete", convert=int, validator=lambda v: v >= 1
        )
        plan = Plan.objects.filter(pk=plan_id).first()
        if not plan:
            self.stdout.write(self.style.ERROR(f"No plan with ID {plan_id}."))
            return
        self.stdout.write(f"    Deleting: {plan.id}  {plan.name} ₹{plan.price} ({plan.period})")
        confirm = prompt(self, "Type 'yes' to confirm deletion", default="no")
        if confirm.lower() != "yes":
            self.stdout.write(self.style.WARNING("Deletion cancelled."))
            return
        try:
            plan.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {plan.name}."))
        except ProtectedError:
            self.stdout.write(
                self.style.ERROR(
                    f"Cannot delete '{plan.name}': it has linked subscriptions/payments. "
                    "Use option 3 with the plans list and set it inactive via the admin instead."
                )
            )
