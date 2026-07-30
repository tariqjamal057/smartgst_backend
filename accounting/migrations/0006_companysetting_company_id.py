import random
import string

from django.db import migrations, models


def gen_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def backfill_company_ids(apps, schema_editor):
    CompanySetting = apps.get_model("accounting", "CompanySetting")
    used = set()
    for row in CompanySetting.objects.all():
        while True:
            cid = gen_id()
            if cid not in used:
                used.add(cid)
                break
        CompanySetting.objects.filter(pk=row.pk).update(company_id=cid)


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0005_companysetting_book_beginning_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysetting",
            name="company_id",
            field=models.CharField(blank=True, default="", max_length=6),
        ),
        migrations.RunPython(backfill_company_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="companysetting",
            name="company_id",
            field=models.CharField(max_length=6, unique=True),
        ),
    ]
