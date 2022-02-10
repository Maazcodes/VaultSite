import time

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from vault.models import TreeNode


class Command(BaseCommand):
    help = "Create a tree of nodes with arguments: depth width"

    def add_arguments(self, parser):
        parser.add_argument("depth", type=int)
        parser.add_argument("width", type=int)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Don't run gen_tree outside of a development environment"
            )

        print(options["depth"], options["width"])

        TreeNode.objects.all().delete()

        start = time.perf_counter()

        current_depth = 1
        nodes = []
        for d in range(options["depth"]):
            if current_depth == 1:
                nodes = TreeNode.objects.bulk_create(
                    TreeNode(
                        parent=None,
                        name="Archive" + str(i),
                        node_type=TreeNode.Type.ORGANIZATION,
                    )
                    for i in range(options["width"])
                )
                current_depth += 1
                continue
            new_nodes = []
            if current_depth == 2:
                for node in nodes:
                    new_nodes.extend(
                        TreeNode.objects.bulk_create(
                            TreeNode(
                                parent=node,
                                name=f"depth{current_depth}node{i}",
                                node_type=TreeNode.Type.COLLECTION,
                            )
                            for i in range(options["width"])
                        )
                    )
                nodes = new_nodes
                current_depth += 1
                continue
            if current_depth <= options["depth"] - 1:
                for node in nodes:
                    new_nodes.extend(
                        TreeNode.objects.bulk_create(
                            TreeNode(
                                parent=node,
                                name=f"depth{current_depth}node{i}",
                                node_type=TreeNode.Type.FOLDER,
                            )
                            for i in range(options["width"])
                        )
                    )
                nodes = new_nodes
                current_depth += 1
                continue
            for node in nodes:
                new_nodes.extend(
                    TreeNode.objects.bulk_create(
                        TreeNode(parent=node, name=f"depth{current_depth}node{i}")
                        for i in range(options["width"])
                    )
                )
            nodes = new_nodes
            current_depth += 1

        end = time.perf_counter()
        self.stdout.write(f"Time taken {end - start}")
