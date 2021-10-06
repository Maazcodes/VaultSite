import os
import re
import unicodedata
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from vault.models import Collection, Deposit, DepositFile, File, User


def gen_flow_identifier(file):
    identifier = unicodedata.normalize("NFKC", file.client_filename)
    identifier = re.sub(r"[^\w\s-]", "", identifier.lower())
    identifier = re.sub(r"[-\s]+", "-", identifier).strip("-_")
    return str(file.size) + "-" + identifier


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
            self.style.SUCCESS(
                f'User found: "{user.id}": {user.username}'
            )
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
                for file in files:
                    flow_identifier = gen_flow_identifier(file)
                    chunk_file_path = os.path.join(osfs_root, "chunks", flow_identifier) + "-1.tmp"
                    deposit_files.append(
                        DepositFile(
                            deposit=deposit,
                            flow_identifier=flow_identifier,
                            name=os.path.split(file.client_filename)[1],
                            relative_path=file.client_filename,
                            size=file.size,
                            type="",
                            pre_deposit_modified_at=file.creation_date,
                        )
                    )
                    try:
                        os.link(file.staging_filename, chunk_file_path)
                    except FileExistsError as e:
                        self.stdout.write(
                            self.style.WARNING(f"Destination chunk file already exists {chunk_file_path}")
                        )
                DepositFile.objects.bulk_create(deposit_files)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deposit created. id:{deposit.id}. {len(deposit_files)} files are in place. Please set DepositFile entries to UPLOADED to begin processing"
                    )
                )
