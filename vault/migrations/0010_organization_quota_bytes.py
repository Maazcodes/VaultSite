# Generated by Django 3.2.3 on 2021-06-23 21:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0009_auto_20210623_2110"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="quota_bytes",
            field=models.PositiveBigIntegerField(default=42),
        ),
    ]
