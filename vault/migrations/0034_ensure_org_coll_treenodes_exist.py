# pylint: disable=invalid-name
# Generated by Django 3.2.9 on 2022-03-30 19:09

from django.db import migrations


def _ensure_organization_treenodes_exist(apps, schema_editor):
    Organization = apps.get_model("vault", "Organization")
    TreeNode = apps.get_model("vault", "TreeNode")
    db_alias = schema_editor.connection.alias

    orgs_without_treenodes = Organization.objects.using(db_alias).filter(
        tree_node__isnull=True
    )

    for org in orgs_without_treenodes:
        treenode = TreeNode.objects.using(db_alias).create(
            node_type="ORGANIZATION",
            parent=None,
            name=org.name,
        )
        org.tree_node_id = treenode.id
        org.save()


def _ensure_collection_treenodes_exist(apps, schema_editor):
    Collection = apps.get_model("vault", "Collection")
    TreeNode = apps.get_model("vault", "TreeNode")
    db_alias = schema_editor.connection.alias

    collections_without_treenodes = Collection.objects.using(db_alias).filter(
        tree_node__isnull=True
    )

    for collection in collections_without_treenodes:
        org = collection.organization
        org_treenode = org.tree_node
        treenode = TreeNode.objects.using(db_alias).create(
            node_type="COLLECTION",
            parent=org_treenode,
            name=collection.name,
        )
        collection.tree_node_id = treenode.id
        collection.save()


class Migration(migrations.Migration):
    """Adds Deposit.parent_node_id  and backfills ids from Collection-related
    Treenode ids.
    """

    dependencies = [
        ("vault", "0033_treenode_file_accounting_triggers"),
    ]

    operations = [
        # 2. ensure all Organizations have associated TreeNodes
        migrations.RunPython(
            code=_ensure_organization_treenodes_exist,
            reverse_code=migrations.RunPython.noop,
        ),
        # 3. ensure all Collections have associated TreeNodes
        migrations.RunPython(
            code=_ensure_collection_treenodes_exist,
            reverse_code=migrations.RunPython.noop,
        ),
    ]