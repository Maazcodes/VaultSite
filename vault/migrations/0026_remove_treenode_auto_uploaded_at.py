# Generated by Django 3.2.3 on 2021-10-08 18:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0025_directory_to_folder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="treenode",
            name="uploaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]