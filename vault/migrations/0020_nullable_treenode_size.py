# Generated by Django 3.2.3 on 2021-09-20 21:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0019 treenode indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="treenode",
            name="size",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
