"""

DOAJ TreeNode Table Update WT-1139
==================================

Creates `TreeNode` entries for a given collection. Safe to run repeatedly: if a
`TreeNode` entry already exists (checked by sha256), this command will stop
immediately; example use:

    $ python manage.py doaj_update_treenode --organization-id 1 --colection-id 198

If some `TreeNode` entries for a collection already exists, but some do not, you
can use `--force` to create the missing ones. This is still idempotent - no new
entry is created for files which are matched by sha256.

    $ python manage.py doaj_update_treenode --force --organization-id 1 --colection-id 198

Notes
=====

We assume flat files, that is, we add files below a collection (no folders).

We only need this until the uploader is rewritten; probably ok to just
semi-automate, e.g.

    $ python manage.py doaj_upload --organization-id 1 --collection-id 198
    $ python manage.py doaj_update_treenode --organization-id 1 --collection-id 198

"""
import collections
import hashlib
import os
import pprint

from django.core.management.base import BaseCommand, CommandError

from vault.models import Collection, File, TreeNode


def md5hex(filename, bufsize=4096):
    """
    Return the MD5 hexdigest for a given file.
    """
    # TODO: this may live elsewhere, in some util module
    hasher = hashlib.md5()
    with open(filename, "rb") as f:
        for b in iter(lambda: f.read(bufsize), b""):
            hasher.update(b)
    return hasher.hexdigest()


class Command(BaseCommand):
    help = "Update treenodes for collections with legacy uploads"

    def add_arguments(self, parser):
        parser.add_argument(
            "-c",
            "--collection-id",
            type=int,
            help="collection for which files should get treenode entries",
            required=True,
        )
        parser.add_argument(
            "--organization-id",
            type=int,
            help="the org we expect the collection belongs to; DOAJ=1 (prod)",
            default=1,
            required=True,
        )
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help="just report what would be added to the database",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="continue adding missing treenodes, even if some are already present",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        collection_id = options["collection_id"]
        organization_id = options["organization_id"]

        try:
            collection = Collection.objects.get(
                pk=collection_id, organization=organization_id
            )
        except Collection.DoesNotExist as exc:
            raise CommandError(exc)
        files = File.objects.filter(collection_id=collection_id)
        if len(files) == 0:
            raise CommandError(f"no files found for collection {collection_id}")

        # dummy, to catch any i/o errors first
        Node = collections.namedtuple(
            "Node",
            [
                "name",
                "parent_id",
                "node_type",
                "md5_sum",
                "sha1_sum",
                "sha256_sum",
                "size",
                "file_type",
                "uploaded_by_id",
                "modified_at",
                "uploaded_at",
                "pre_deposit_modified_at",
            ],
        )
        nodes = []
        for f in files:
            md5_sum = md5hex(f.staging_filename)
            if f.md5_sum != md5_sum:
                raise CommandError(
                    f"hash mismatch in {f.staging_filename}: {f.md5_sum} {md5_sum}"
                )
            name = os.path.basename(f.staging_filename)
            # TODO: pre_deposit_modified_at, modified_at, file_type
            # pre_deposit_modified_at seems like the modification time of the
            # file pre-upload? Do we even have this for files?
            node = Node(
                name=name,
                parent_id=collection.tree_node.id,
                node_type=TreeNode.Type.FILE,
                md5_sum=f.md5_sum,
                sha1_sum=f.sha1_sum,
                sha256_sum=f.sha256_sum,
                size=os.path.getsize(f.staging_filename),
                uploaded_at=f.creation_date,
                uploaded_by_id=f.uploaded_by_id,
                file_type=None,
                modified_at=None,
                pre_deposit_modified_at=None,
            )
            nodes.append(node)

        if dry_run:
            for node in nodes:
                pprint.pprint(node._asdict())
            return

        additions = []  # collect nodes that we want to add
        for node in nodes:
            try:
                obj = TreeNode.objects.get(sha256_sum=node.sha256_sum)
            except TreeNode.DoesNotExist:
                additions.append(node)
            else:
                if not force:
                    raise CommandError(
                        f"an entry already exists for {node.name}: {obj}, use --force to skip"
                    )
        TreeNode.objects.bulk_create([TreeNode(**node._asdict()) for node in additions])
        self.stdout.write(
            self.style.SUCCESS(
                f"updated {len(additions)} treenodes for collection {collection_id}"
            )
        )
