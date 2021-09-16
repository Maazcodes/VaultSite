# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-04 16:48
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("vault", "0012_deposit_depositfile"),
    ]

    operations = [
        migrations.CreateModel(
            name="TreeNode",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.TextField()),
                (
                    "parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="vault.TreeNode",
                    ),
                ),
            ],
        ),
    ]
