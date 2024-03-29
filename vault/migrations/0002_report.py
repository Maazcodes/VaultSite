# Generated by Django 3.2.3 on 2021-06-06 21:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Report",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField()),
                ("total_size", models.PositiveBigIntegerField()),
                ("file_count", models.PositiveBigIntegerField()),
                ("error_count", models.PositiveBigIntegerField()),
                ("missing_location_count", models.PositiveBigIntegerField()),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="vault.collection",
                    ),
                ),
            ],
        ),
    ]
