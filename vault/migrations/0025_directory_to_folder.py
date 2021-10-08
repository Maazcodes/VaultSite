# Generated by Django 3.2.3 on 2021-10-07 03:18

from django.db import migrations

from vault.models import TreeNode


def directory_to_folder(apps, schema_editor):
    """Move TreeNode.node_type from DIRECTORY to FOLDER."""
    # We can't import the TreeNode model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    for node in TreeNode.objects.all():
        if node.node_type == "DIRECTORY":
            node.node_type = TreeNode.Type.FOLDER
            node.save()


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0024_auto_20210924_1752"),
    ]

    operations = [
        migrations.RunPython(directory_to_folder),
    ]