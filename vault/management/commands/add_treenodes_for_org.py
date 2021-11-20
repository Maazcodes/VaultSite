from django.core.management.base import BaseCommand

from vault.models import Organization, Collection, TreeNode


class Command(BaseCommand):
    help = "Create missing ORGANIZATION and COLLECTION TreeNodes for a given Org ID"

    def add_arguments(self, parser):
        parser.add_argument("organization_id", type=int, help="The Organization ID")

    def handle(self, *args, **options):
        org = Organization.objects.get(id=options["organization_id"])
        add_treenodes_for_org(org)


def add_treenodes_for_org(org):
    if not org.tree_node:
        org_node, created = TreeNode.objects.get_or_create(
            node_type=TreeNode.Type.ORGANIZATION, name=org.name
        )
        org.tree_node = org_node
        org.save()
        if created:
            print(
                f"New ORGANIZATION TreeNode {org_node.id} created and linked to {org.name} - {org.id}"
            )
        else:
            print(
                f"Existing ORGANIZATION TreeNode {org_node.id} linked to {org.name} - {org.id}"
            )
    collections = Collection.objects.filter(organization=org)
    for coll in collections:
        if not coll.tree_node:
            coll_node, created = TreeNode.objects.get_or_create(
                node_type=TreeNode.Type.COLLECTION, name=coll.name, parent=org.tree_node
            )
            coll.tree_node = coll_node
            coll.save()
            if created:
                print(
                    f"New COLLECTION TreeNode {coll_node.id} created and linked to {coll.name} - {coll.id}"
                )
            else:
                print(
                    f"Existing COLLECTION TreeNode {coll_node.id} linked to {coll.name} - {coll.id}"
                )
