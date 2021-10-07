import os
import re
import unicodedata
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from vault.models import (
    Collection,
    Deposit,
    DepositFile,
    File,
    Organization,
    TreeNode,
    User,
)


def gen_flow_identifier(file):
    identifier = unicodedata.normalize("NFKC", file.client_filename)
    identifier = re.sub(r"[^\w\s-]", "", identifier.lower())
    identifier = re.sub(r"[-\s]+", "-", identifier).strip("-_")
    return str(file.size) + "-" + identifier


def find_parent_node(deposit_file):
    organization = Organization.objects.get(id=deposit_file.deposit.organization_id)
    collection = Collection.objects.get(id=deposit_file.deposit.collection_id)

    # Make collection and org tree nodes if non existent
    if organization.tree_node is None:
        return None
    if collection.tree_node is None:
        return None

    # filter and ignore empty path segments. Strip file name segment
    parent_segment = collection.tree_node
    for segment in filter(None, deposit_file.relative_path.split("/")[:-1]):
        try:
            parent_segment = TreeNode.objects.get(
                parent=parent_segment, name=segment, node_type=TreeNode.Type.DIRECTORY
            )
        except TreeNode.DoesNotExist:
            return None

    return parent_segment


class Command(BaseCommand):
    help = "Migrates files from vault.models.File into a Deposit for re-ingestion."

    def add_arguments(self, parser):
        parser.add_argument(
            "user_id", type=int, help="User ID to associate with the Deposit"
        )
        parser.add_argument("collection_ids", nargs="+", type=int)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(id=options["user_id"])
        except User.DoesNotExist:
            raise CommandError(f'User {options["user_id"]} does not exist')
        self.stdout.write(
            self.style.SUCCESS(f'User found: "{user.id}": {user.username}')
        )

        for collection_id in options["collection_ids"]:
            try:
                collection = Collection.objects.get(pk=collection_id)
            except Collection.DoesNotExist:
                raise CommandError('Collection "%s" does not exist' % collection_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Collection found: "{collection_id}": {collection.name}'
                )
            )

            files = File.objects.filter(collection=collection_id)
            if len(files) == 0:
                self.stdout.write(
                    self.style.WARNING(f"No files found for collection {collection_id}")
                )
            else:
                print("Collection files found. Creating Deposit...")
                deposit = Deposit.objects.create(
                    organization_id=collection.organization_id,
                    collection=collection,
                    user=user,
                )
                org_tmp_path = str(collection.organization_id)
                osfs_root = os.path.join(settings.FILE_UPLOAD_TEMP_DIR, org_tmp_path)

                deposit_files = []
                skipped_files = []
                for file in files:
                    flow_identifier = gen_flow_identifier(file)
                    chunk_file_path = (
                        os.path.join(osfs_root, "chunks", flow_identifier) + "-1.tmp"
                    )

                    # todo don't make deposit file if Treenode already exists!
                    # todo Warn if this happens!

                    deposit_file = DepositFile(
                        deposit=deposit,
                        flow_identifier=flow_identifier,
                        name=os.path.split(file.client_filename)[1],
                        relative_path=file.client_filename,
                        size=file.size,
                        type="",
                    )

                    # Don't make DepositFile if TreeNode already exists. Will need to handle these separately
                    parent_tree_node = find_parent_node(deposit_file)
                    if parent_tree_node is not None and 0 != len(
                        TreeNode.objects.filter(
                            parent=parent_tree_node, name=deposit_file.name
                        )
                    ):
                        skipped_files.append(file)
                        self.stdout.write(
                            self.style.WARNING(
                                f"TreeNode entry already exists for vault File id:{file.id} - Skipping..."
                            )
                        )
                        continue
                    else:
                        deposit_files.append(deposit_file)

                    try:
                        os.link(file.staging_filename, chunk_file_path)
                    except FileExistsError as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Destination chunk file already exists {chunk_file_path}"
                            )
                        )
                if len(deposit_files) == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"No deposit files created."
                        )
                    )
                else:
                    DepositFile.objects.bulk_create(deposit_files)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Deposit created. id:{deposit.id}. {len(deposit_files)} files are in place. Please set DepositFile entries to UPLOADED to begin processing"
                        )
                    )
                if len(skipped_files) > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{len(skipped_files)} files skipped due to TreeNode already existing. Listing files:"
                        )
                    )
                    for file in skipped_files:
                        self.stdout.write(
                            self.style.WARNING(
                                f"\tID:{file.id} - {file.client_filename} - {file.sha256_sum}"
                            )
                        )
