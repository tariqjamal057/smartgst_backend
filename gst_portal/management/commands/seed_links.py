"""Seed the dashboard Important Links & Important Portals.

Run: python manage.py seed_links [--dynamic] [--count N]

Exactly two modes:
- Default:  seed the predefined static dataset (the govt. GST links/portals).
- --dynamic --count N:  generate ``N`` many synthetic dynamic entries spread
  across both sections (links and portals) for demos / load testing.

Static seeding is idempotent (existing kind+url rows are skipped/kept).

Examples:
  poetry run python manage.py seed_links
  poetry run python manage.py seed_links --dynamic --count 40
"""

from django.core.management.base import BaseCommand

from gst_portal.models import DashboardLink

STATIC_LINKS = [
    {"label": "News & Updates", "url": "https://www.gst.gov.in/newsandupdates", "icon": "🖥️"},
    {"label": "Popular Help Topics", "url": "https://www.gst.gov.in/help", "icon": "🌐"},
    {"label": "GST Media Youtube", "url": "https://www.youtube.com/@CBIC-GST", "icon": "▶️"},
    {"label": "GST Notifications", "url": "https://www.gst.gov.in/notification", "icon": "📋"},
]

STATIC_PORTALS = [
    {"label": "GST Portal", "url": "https://www.gst.gov.in", "icon": "🏛️"},
    {"label": "E-Way Bill Portal", "url": "https://ewaybillgst.gov.in", "icon": "📦"},
    {"label": "E-Invoice Portal", "url": "https://einvoice1.gst.gov.in", "icon": "📄"},
    {"label": "Grievance Portal", "url": "https://selfservice.gstsystem.in", "icon": "⚖️"},
    {"label": "CBIC Portal", "url": "https://cbic.gov.in", "icon": "🏦"},
]

LINK_ICONS = ["🔗", "🌐", "📌", "⚡", "🎯", "🧭", "💡", "🆕"]
PORTAL_ICONS = ["🏛️", "🏦", "📊", "🗂️", "🧾", "🖧", "🛡️", "✨"]


def dynamic_items(count):
    """Build ``count`` synthetic link/portal entries."""
    items = []
    for i in range(count):
        is_portal = i % 3 == 0  # ~1 in 3 is a portal
        icons = PORTAL_ICONS if is_portal else LINK_ICONS
        kind = DashboardLink.KIND_PORTAL if is_portal else DashboardLink.KIND_LINK
        if is_portal:
            label = f"Govt. Portal {i + 1} - Tax module {i % 7 + 1}"
            url = f"https://portal{i + 1}.gov.in"
        else:
            label = f"Important Resource {i + 1} - Compliance help {i % 5 + 1}"
            url = f"https://gst.gov.in/resource-{i + 1}"
        items.append(
            {
                "kind": kind,
                "label": label,
                "url": url,
                "icon": icons[i % len(icons)],
                "sort_order": i,
                "is_active": True,
            }
        )
    return items


class Command(BaseCommand):
    help = "Seed dashboard Important Links & Important Portals (static or dynamic)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dynamic",
            action="store_true",
            help="Generate many synthetic entries instead of the static dataset.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=40,
            help="How many entries for --dynamic (default: 40).",
        )

    def handle(self, *args, **options):
        if options["dynamic"]:
            items = dynamic_items(options["count"])
            DashboardLink.objects.bulk_create([DashboardLink(**data) for data in items])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done: {len(items)} dynamic entries created. Total now: "
                    f"{DashboardLink.objects.count()}."
                )
            )
            return

        created = 0
        for kind, statics in (
            (DashboardLink.KIND_LINK, STATIC_LINKS),
            (DashboardLink.KIND_PORTAL, STATIC_PORTALS),
        ):
            for order, data in enumerate(statics):
                _, was_created = DashboardLink.objects.get_or_create(
                    kind=kind,
                    url=data["url"],
                    defaults={**data, "sort_order": order},
                )
                created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} static item(s) created / "
                f"{len(STATIC_LINKS) + len(STATIC_PORTALS)} in dataset. Total now: "
                f"{DashboardLink.objects.count()}."
            )
        )
