"""

DOAJ Upload Helper WT-1139
==========================

Copies files associated with a (legacy) vault collection - currently only of
organization "DOAJ" - into a petabox item.

By default, we upload to https://archive.org/details/ProjectJasperTransfers.
You can run this multiple times with the same parameters (we either upload or verify).

Assume that `vault/management/commands/migrate_vaultfiles_to_deposit.py` has
been run for any previous "File" uploads.

Usage example (remove --dry-run, add --item-collection "ProjectJasperTransfers"):

    $ python manage.py doaj_upload
            --dry-run
            --organization-id 1
            --collection-id 246
            --item-identifier Alphaville_2009-4078
            --item-title "Alphaville 2009-4078"
            --item-collection ""
            -c ~/.config/ia.ini

Local example:

    $ AIT_CONF=./DPS_dev/vault.yml ./venv/bin/python manage.py doaj_upload
            --dry-run
            --collection-id 246
            --item-identifier TEST_VAULT_Alphaville_2009-4078
            --item-title "TEST VAULT Alphaville 2009-4078"
            --item-collection ""
            --organization-id 1
            -c ~/.config/ia.ini

Nothing, that could not be done with "ia upload", we just get filenames
directly from the database.

    $ ia -c /opt/DPS/ia.ini upload Alphaville_2009-4078
            --metadata="mediatype:data"
            --metadata='title:Alphaville 2009-4078'
            --metadata="collection:ProjectJasperTransfers"
            --metadata="noindex:true"
            --metadata="creator:vault_uploader"
            20094078-2022-01-20-10-44-57.tar.gz
            20094078-2022-01-20-11-09-18.tar.gz
            20094078-2022-01-20-11-18-36.tar.gz
            20094078-2022-01-20-16-17-37.tar.gz
            20094078-2022-02-21-11-59-55.tar.gz

Scope
=====

We only need this until the "deposit_web" uploader is rewritten; probably ok to
just semi-automate.

"""

import hashlib
import os
import logging
import textwrap

import internetarchive as ia
from django.core.management.base import BaseCommand, CommandError

from vault.models import Collection, File

logger = logging.getLogger("doaj-upload")


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


def item_exists(item_identifier):
    """
    Returns true, if an archive item exists.
    """
    return bool(ia.get_item(item_identifier).item_metadata)


def verify_item_files(item_identifier, filenames):
    """
    Raises exceptions on any consistency issue between a list of files
    and the files in a given petabox item.
    """
    item = ia.get_item(item_identifier)
    if not item:
        raise ValueError(f"item not found: {item_identifier}")
    local = {(os.path.basename(fn), md5hex(fn)) for fn in filenames}
    uploaded = {
        (fi["name"], fi["md5"])
        for fi in item.files
        if all(k in fi for k in ("name", "md5"))
    }
    diff = local - uploaded
    if len(diff) > 0:
        msg = textwrap.dedent(
            f"""
            Files missing or mismatched in petabox
            Item   : {item_identifier}
            Diff   : {diff}
            Local  : {local}
            Petabox: {uploaded}

            Note: There is a delay (minutes, typically) until metadata becomes visible in petabox.
                  Not all errors may indeed be errors.
        """
        )
        raise ValueError(msg)


def upload_item(
    item_identifier,
    filenames,
    title=None,
    collection="ProjectJasperTransfers",
    ia_config_file="/opt/DPS/ia.ini",
    metadata=None,
):
    """
    Upload a list of files to an item (created, if necessary). If the item
    exists, metadata is not modified.
    """
    if not all((item_identifier, ia_config_file)):
        raise ValueError("incomplete data for upload")
    title = item_identifier if title is None else title
    if metadata is None:
        metadata = {
            "title": title,
            "collection": collection,
            "mediatype": "data",
            "noindex": "true",
            "creator": "vault_uploader",
        }
    sess = ia.get_session(config_file=ia_config_file)
    ia.upload(
        item_identifier,
        filenames,
        access_key=sess.access_key,
        secret_key=sess.secret_key,
        verify=True,
        verbose=True,
        checksum=True,
        delete=False,
        retries=3,
        validate_identifier=True,
        metadata=metadata,
    )


class Command(BaseCommand):
    help = "Upload DOAJ style uploaded files from vault to petabox"

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            help="the org we expect the collection belongs to (in prod DOAJ=1)",
            default=1,
            required=True,
        )
        parser.add_argument(
            "--collection-id",
            type=int,
            help="vault collection id files to upload belong to",
            required=True,
        )
        parser.add_argument(
            "--item-title",
            type=str,
            help="petabox item title (can be changed manually later)",
            required=True,
        )
        parser.add_argument(
            "--item-identifier",
            type=str,
            help="petabox item identifier (cannot be changed)",
            required=True,
        )
        parser.add_argument(
            "--item-collection",
            type=str,
            help="collection to put item under",
            default="ProjectJasperTransfers",
            required=True,
        )
        parser.add_argument(
            "-c",
            "--config-file",
            type=str,
            help="path to ia.ini",
            default="/opt/DPS/ia.ini",
            required=True,
        )
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help="just report what would happen",
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="force re-upload, even if item already exists (no metadata change)",
        )

    def handle(self, *args, **options):
        collection_id = options["collection_id"]
        config_file = options["config_file"]
        dry_run = options["dry_run"]
        force = options["force"]
        item_identifier = options["item_identifier"]
        item_title = options["item_title"]
        item_collection = options["item_collection"]
        organization_id = options["organization_id"]

        if dry_run:
            logger.debug("running in dry-run noop mode")

        try:
            collection = Collection.objects.get(
                pk=collection_id, organization=organization_id
            )
        except (Organization.DoesNotExist, Collection.DoesNotExist) as exc:
            raise CommandError(exc)

        # find files for collection
        files = File.objects.filter(collection_id=collection_id)
        filenames = [f.staging_filename for f in files if f.staging_filename]
        if len(filenames) == 0:
            raise CommandError(f"no files found for collection: {collection_id}")

        if not item_exists(item_identifier) or force:
            try:
                if dry_run:
                    logger.debug(f"using: {config_file}")
                    logger.debug(f"uploading to: {item_identifier} {item_title}")
                    for f in filenames:
                        logger.debug(f)
                else:
                    logger.debug(
                        f"uploading {len(filenames)} file(s) to {item_identifier} ..."
                    )
                    for fn in filenames:
                        logger.debug(fn)
                    upload_item(
                        item_identifier,
                        filenames,
                        title=item_title,
                        collection=item_collection,
                        ia_config_file=config_file,
                    )
            except Exception as exc:
                raise CommandError(f"upload failed {item_identifier}: {exc}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"successfully uploaded {len(filenames)} file(s) to {item_identifier} for collection {collection_id}"
                    )
                )
                logger.info(
                    "note: skipping verification after upload, since files may not be immediately visible"
                )
                return

        try:
            # If we verify immediately after an item upload, metadata will
            # likely not be available right away, and this would fail.
            verify_item_files(item_identifier, filenames)
        except ValueError as exc:
            raise CommandError(f"verification failed {item_identifier}: {exc}")
        else:
            self.stdout.write(self.style.SUCCESS(f"ok: {item_identifier}"))
