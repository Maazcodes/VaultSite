# This process handles merged/hashed deposit files.
# We will create TreeNode Entries and then shuffle file into its final resting place

import argparse
import logging
import os
import shutil
import signal
import sys
import hashlib
import threading
from fs.osfs import OSFS
from internetarchive import Item, get_session

os.environ["DJANGO_SETTINGS_MODULE"] = "vault_site.settings"
import django

sys.path.append(os.path.join("..", os.getcwd()))
django.setup()
from django.conf import settings
from django.utils import timezone, dateformat
from vault.models import DepositFile, Deposit, TreeNode, Collection, Organization

SLEEP_TIME = 20
MAX_PBOX_ITEM_FILES = 10000
MAX_PBOX_ITEM_BYTES = 100 * 1024 * 1024 * 1024  # 100GiB

logger = logging.getLogger(__name__)

shutdown = threading.Event()

# For each hashed file
# check TreeNode for petabox path
# if none; upload to pbox
# if pbox path update status of DepositFile and Deposit


def process_hashed_deposit_files():

    while True:
        for deposit_file in DepositFile.objects.filter(
            state=DepositFile.State.HASHED
        ).order_by("id"):
            org_id = deposit_file.deposit.organization_id
            org_tmp_path = str(org_id)

            # Check if we have the hashed file. It may be on another node.
            sha_file_path = os.path.join(
                get_shafs_folder(deposit_file), deposit_file.sha256_sum
            )

            if not os.path.isfile(path=sha_file_path):
                continue

            if deposit_file.tree_node and not deposit_file.tree_node.pbox_item:
                status_code, item_name = try_upload_to_pbox(deposit_file, sha_file_path)
                if status_code == 200:
                    deposit_file.tree_node.pbox_item = item_name
                    deposit_file.tree_node.save()
                    logger.info(
                        f"Upload success. Status:{status_code} - item {item_name}/{deposit_file.sha256_sum}"
                    )
                else:
                    logger.error(
                        f"Error uploading to petabox. Status:{status_code} - item {item_name}/{deposit_file.sha256_sum}"
                    )
                    if status_code == 503:
                        logger.error(
                            f"Petabox returning 503 Slow Down. Taking a break."
                        )
                        if shutdown.wait(2 * SLEEP_TIME):
                            return
                        continue

            if deposit_file.tree_node and deposit_file.tree_node.pbox_item:
                deposit_file.state = DepositFile.State.REPLICATED
                deposit_file.save()

                # if all deposit_files in this deposit are REPLICATED, then set Deposit.state=REPLICATED
                # todo should this just be a trigger on deposit_file.state?
                if 0 == len(
                    DepositFile.objects.filter(
                        deposit=deposit_file.deposit,
                        state__in=(
                            DepositFile.State.REGISTERED,
                            DepositFile.State.UPLOADED,
                            DepositFile.State.HASHED,
                        ),
                    )
                ):
                    deposit_file.deposit.state = Deposit.State.REPLICATED
                    deposit_file.deposit.save()

        logger.debug(f"forever loop sleeping {SLEEP_TIME} sec before iterating")
        if shutdown.wait(SLEEP_TIME):
            return


# TODO expand this in the future for shafs folder structure
def get_shafs_folder(deposit_file):
    org_id = deposit_file.deposit.organization_id
    org_tmp_path = str(org_id)
    return os.path.join(settings.SHADIR_ROOT, org_tmp_path)


def try_upload_to_pbox(deposit_file, file_path):
    org_id = deposit_file.deposit.organization_id
    col_id = deposit_file.deposit.collection_id

    item_name = get_pbox_item_name(deposit_file)
    logger.info(
        f"Uploading file to petabox: {item_name}/{deposit_file.sha256_sum} - {deposit_file.size} bytes"
    )
    if item_name is not None:
        if not os.path.isfile(settings.IA_CONFIG_PATH):
            logger.error(f"IA config path not found: {settings.IA_CONFIG_PATH}")
            return 0, None
        ia_session = get_session(config_file=settings.IA_CONFIG_PATH)
        item = ia_session.get_item(item_name)

        metadata = dict(
            collection=deposit_file.deposit.organization.pbox_collection,
            mediatype="data",
            creator="Vault",
            description=f"Data files for Vault digital preservation service - {org_id}",
        )
        headers = {"x-archive-check-file": "0"}
        responses = []
        try:
            responses = item.upload(
                file_path,
                queue_derive=False,
                verify=True,
                metadata=metadata,
                headers=headers,
            )
        except Exception as e:
            logger.error(f"Error uploading to petabox: {e}")

        if responses and len(responses) == 1:
            return responses[0].status_code, item_name
        else:
            return 0, item_name
    else:
        return 0, None


# Return the first pbox item that has room whether it exists or not.
def get_pbox_item_name(deposit_file):
    if deposit_file.deposit.organization.pbox_collection is None:
        logger.error(
            f"Deposit organization has no petabox collection set: organization.id={deposit_file.deposit.organization.id}"
        )
        return None
    org_id = deposit_file.deposit.organization_id
    datestamp = dateformat.format(timezone.now(), "Ymd")
    environment = (
        "-" + settings.DEPLOYMENT_ENVIRONMENT
        if settings.DEPLOYMENT_ENVIRONMENT != "PROD"
        else ""
    )
    prefix = f"DPS-VAULT{environment}-{org_id}-{datestamp}"
    count = 1

    ia_session = get_session(config_file=settings.IA_CONFIG_PATH)

    while True:
        item_name = prefix + f"-{count:05d}"
        item = ia_session.get_item(item_name)
        if not item.exists:
            return item_name
        else:
            if (item.item_size is not None and item.files_count is not None) and (
                item.item_size > MAX_PBOX_ITEM_BYTES
                or item.files_count > MAX_PBOX_ITEM_FILES
            ):
                count += 1
                continue
            else:
                return item_name


def main(argv=None):
    argv = argv or sys.argv
    arg_parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]),
        description="%s - Vault - Process Hashed Files" % (os.path.basename(argv[0])),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    arg_parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        action="store_const",
        default=logging.INFO,
        const=logging.DEBUG,
        help="verbose logging",
    )
    args = arg_parser.parse_args(args=sys.argv[1:])

    logging.root.setLevel(level=args.log_level)
    logging_handler = logging.StreamHandler()
    logging_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    logging_handler.setFormatter(logging_formatter)
    logger.addHandler(logging_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGHUP, sig_handler)
    signal.signal(signal.SIGQUIT, sig_handler)

    process_hashed_deposit_files()


def sig_handler(signum, frame):
    logging.info("shutting down (caught signal %s)", signum)
    shutdown.set()


if __name__ == "__main__":
    main()
