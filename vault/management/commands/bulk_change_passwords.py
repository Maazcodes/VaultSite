#!/usr/bin/env python3

import argparse
import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from vault.models import User


class Command(BaseCommand):
    help = "Sets passwords for users using input from a CSV file"

    def add_arguments(self, parser):
        # Note: `user_pass_csv` is a CSV-formatted text file which explicitly
        # does *not* begin with a field name row. That is, all rows in this
        # file must be data rows
        parser.add_argument(
            "user_pass_csv",
            type=argparse.FileType("r", encoding="UTF-8"),
            help="path to CSV file containing usernames and passwords",
        )

    def handle(self, *args, **options):
        csv_file = options["user_pass_csv"]
        reader = csv.DictReader(
            csv_file,
            fieldnames=("username", "password"),
        )

        with transaction.atomic():
            for row in reader:
                username = row["username"]
                password = row["password"]
                assert username is not None
                assert password is not None, f"password for {username} is None"

                user = User.objects.get(username=username)
                user.set_password(password)
                user.save()

        self.stdout.write(self.style.SUCCESS("Done"))
