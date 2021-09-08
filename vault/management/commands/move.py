import json
from typing import Text
import time

from django.core.management.base import BaseCommand, CommandError
from vault.models import TreeNode


class Command(BaseCommand):
    help = "Create a tree of nodes with arguments: depth width"

    def add_arguments(self, parser):
        parser.add_argument("source", type=int)
        parser.add_argument("destination", type=int)

    def handle(self, *args, **options):
        print(options["source"], options["destination"])

        start = time.perf_counter()

        # 442331 -> 442221

        TreeNode.objects.filter(id=options["source"]).update(
            parent_id=options["destination"]
        )

        end = time.perf_counter()
        self.stdout.write(f"Time taken {end - start}")
