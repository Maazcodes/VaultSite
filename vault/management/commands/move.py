import time

from django.core.management.base import BaseCommand
from django.conf import settings

from vault.models import TreeNode


class Command(BaseCommand):
    help = "Move a TreeNode with id 'source' to a new parent with id 'destination'"

    if not settings.DEBUG:
        print("Don't run move outside of a development environment")
        quit()

    def add_arguments(self, parser):
        parser.add_argument("source", type=int)
        parser.add_argument("destination", type=int)

    def handle(self, *args, **options):
        print(options["source"], options["destination"])

        start = time.perf_counter()

        TreeNode.objects.filter(id=options["source"]).update(
            parent_id=options["destination"]
        )

        end = time.perf_counter()
        self.stdout.write(f"Time taken {end - start}")
