# Generated by Django 3.2.9 on 2022-03-04 00:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0031_fixity_report_json"),
    ]

    operations = [
        migrations.AddField(
            model_name="treenode",
            name="file_count",
            field=models.PositiveBigIntegerField(blank=True, default=0),
        ),
    ]
