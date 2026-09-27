"""Seed (or clear) the News & Updates feed.

Run: python manage.py seed_news [--seed] [--delete-all] [--dynamic] [--count N]

Modes:
- Default (or ``--seed``):      seed the predefined dataset from
                                 ``gst_portal/news_seed_data.py`` (idempotent -
                                 existing titles are skipped).
- ``--delete-all``:              empty the NewsArticle table first.
- ``--dynamic --count N``:       generate ``N`` synthetic articles across all six
                                 types (Notification / Advisory / Revenue Update /
                                 Circular / Update / Press Release) over a
                                 2017-2026 timeline, for demos and load testing.

Flags combine, e.g.:
  python manage.py seed_news --delete-all --seed
  python manage.py seed_news --delete-all --dynamic --count 50
"""

from django.core.management.base import BaseCommand

from gst_portal.models import NewsArticle
from gst_portal.news_seed_data import NEWS_ITEMS

MONTH_NAMES = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
NEWS_TYPES = [
    "Notification",
    "Advisory",
    "Revenue Update",
    "Circular",
    "Update",
    "Press Release",
]
TAGS = [
    "Returns",
    "ITC",
    "E-Invoice",
    "E-Way Bill",
    "Portal",
    "Council",
    "Rates",
    "Exemption",
    "Compliance",
    "Revenue",
    "Exports",
    "Registration",
]


def dynamic_items(count):
    """Build ``count`` synthetic articles across types and years."""
    items = []
    for i in range(count):
        news_type = NEWS_TYPES[i % len(NEWS_TYPES)]
        year = 2017 + (i % 10)
        month = (i % 12) + 1
        day = (i % 27) + 1
        month_name = MONTH_NAMES[month - 1]
        big = 100 + ((i * 7) % 75)  # ~ ₹1.00-1.74 lakh crore
        pct = (i * 3) % 14 + 4  # 4-17%
        tag = TAGS[(i // 6) % len(TAGS)]
        featured = i % 10 == 5
        pdf = i % 3 != 0
        published_date = f"{month_name} {day}, {year}"

        if news_type == "Notification":
            title = f"CBIC notifies compliance deadline updates for {published_date}"
            summary = (
                f"Notification effective {day} {month_name} {year} relaxes filing timelines "
                f"and waives late fees for eligible taxpayers across selected HSN categories."
            )
        elif news_type == "Advisory":
            title = f"GSTN advisory on {tag.lower()} reconciliation for {year}"
            summary = (
                f"Guidance issued for taxpayers to align monthly filings with auto-drafted "
                f"ITC statements, reducing mismatches ahead of the {year} compliance calendar."
            )
        elif news_type == "Revenue Update":
            title = f"GST revenue for {month_name} {year} at ₹{big} lakh crore"
            summary = (
                f"Gross GST collections grew {pct}% year-on-year, driven by domestic "
                f"consumption and improved compliance after e-invoicing expansion."
            )
        elif news_type == "Circular":
            title = f"CBIC circular clarifying {tag.lower()} treatment in {year}"
            summary = (
                f"Circular {162 + i}/20{(year - 2000):02d}-GST clarifies valuation, place of "
                f"supply and ITC rules for transactions involving {tag.lower()}."
            )
        elif news_type == "Update":
            title = f"GSTN portal upgrade improves the {tag.lower()} module"
            summary = (
                f"The GSTN platform adds new features for the {tag.lower()} workflow with "
                f"faster reconciliation and bulk processing for {year}."
            )
        else:  # Press Release
            title = f"GST Council meeting {20 + i} - key decisions summary"
            summary = (
                f"The {i + 20}th GST Council meeting recommended {(pct * 3)} amendments, "
                f"rate rationalisation on {10 + i} items, and compliance relief measures "
                f"effective {published_date}."
            )

        items.append(
            {
                "news_type": news_type,
                "published_date": published_date,
                "year": year,
                "month": month,
                "featured": featured,
                "title": title,
                "summary": summary,
                "tag": tag,
                "pdf_available": pdf,
            }
        )
    return items


class Command(BaseCommand):
    help = "Clear and/or seed the News & Updates feed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            action="store_true",
            help="Seed the predefined dataset from news_seed_data.py (default).",
        )
        parser.add_argument(
            "--delete-all",
            action="store_true",
            help="Delete every NewsArticle first.",
        )
        parser.add_argument(
            "--dynamic",
            action="store_true",
            help="Generate synthetic articles instead of the predefined dataset.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=24,
            help="How many synthetic articles to generate for --dynamic (default: 24).",
        )

    def handle(self, *args, **options):
        delete_all = options["delete_all"]

        if options["dynamic"]:
            seed_mode = "dynamic"
        elif options["seed"]:
            seed_mode = "static"
        else:
            seed_mode = None if delete_all else "static"

        if delete_all:
            deleted, _ = NewsArticle.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing article(s)."))

        if seed_mode is None:
            self.stdout.write(
                self.style.SUCCESS(f"NewsArticle total now: {NewsArticle.objects.count()}.")
            )
            return

        items = dynamic_items(options["count"]) if seed_mode == "dynamic" else NEWS_ITEMS

        existing_titles = set(NewsArticle.objects.values_list("title", flat=True))
        created = 0
        to_create = []
        for data in items:
            if data["title"] in existing_titles:
                continue
            to_create.append(NewsArticle(**data))
            existing_titles.add(data["title"])

        if to_create:
            NewsArticle.objects.bulk_create(to_create)
            created = len(to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} article(s) created / {len(items)} in batch. "
                f"NewsArticle total now: {NewsArticle.objects.count()}."
            )
        )
