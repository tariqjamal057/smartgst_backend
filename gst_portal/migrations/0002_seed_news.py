from django.db import migrations

from gst_portal.news_seed_data import NEWS_ITEMS


def seed_news(apps, schema_editor):
    NewsArticle = apps.get_model("gst_portal", "NewsArticle")
    for item in NEWS_ITEMS:
        NewsArticle.objects.get_or_create(
            title=item["title"],
            defaults={
                "news_type": item["news_type"],
                "published_date": item["published_date"],
                "year": item["year"],
                "month": item["month"],
                "featured": item["featured"],
                "summary": item["summary"],
                "tag": item["tag"],
                "pdf_available": item["pdf_available"],
            },
        )


def unseed_news(apps, schema_editor):
    NewsArticle = apps.get_model("gst_portal", "NewsArticle")
    NewsArticle.objects.filter(title__in=[i["title"] for i in NEWS_ITEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("gst_portal", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_news, unseed_news),
    ]