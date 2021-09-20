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
os.environ["DJANGO_SETTINGS_MODULE"] = "vault_site.settings"
import django

sys.path.append(os.path.join("..", os.getcwd()))
django.setup()
from django.conf import settings
from vault.models import DepositFile, Deposit, TreeNode, Collection, Organization

SLEEP_TIME = 20
logger = logging.getLogger(__name__)

shutdown = threading.Event()


def process_hashed_deposit_files():

    # Look for hashed files ready for processing.
    # Mark Deposit done if all deposit files are done
    # TODO trigger on depositfile delete to archive the row
    # create tree node
    # for now parent is collection
    # todo parent will be specified dir in collection maybe
    # create chain directory tree nodes saving along the way
    # create file tree node, save
    # make sure collection has a tree node
    # move file into tree

    while True:
        for deposit_file in DepositFile.objects.filter(
            state=DepositFile.State.HASHED
        ):
            org_id = deposit_file.deposit.organization_id
            org_tmp_path = str(org_id)

            # Check if we have the hashed file. It may be on another node.
            hashed_file_path = os.path.join(settings.FILE_UPLOAD_TEMP_DIR, org_tmp_path, "merged",
                                            deposit_file.flow_identifier + ".merged")
            if os.path.isfile(path=hashed_file_path):
                parent_node = make_or_find_parent_node(deposit_file)
                file_node = make_or_find_file_node(deposit_file, parent_node)
                shafs_root = os.path.join(settings.SHADIR_ROOT, org_tmp_path)
                try:
                    os.makedirs(shafs_root, exist_ok=True)
                    shutil.move(hashed_file_path, os.path.join(shafs_root, deposit_file.sha256_sum))
                    deposit_file.state = DepositFile.State.REPLICATED  # todo is this right?
                    deposit_file.save()
                except OSError as err:
                    logger.error(f"Error writing to destination {shafs_root} - {err}")
                #todo do we archive depositfile now or when deposit is done?
            # todo Rollback to hashed won't work, but rollback to uploaded will

            # If Deposit is state UPLOADED, but all DepositFiles are REPLICATED, mark Deposit REPLICATED
            deposit = deposit_file.deposit
            if deposit.state == Deposit.State.HASHED:
                if 0 == len(DepositFile.objects.filter(deposit=deposit, state__in=(Deposit.State.REGISTERED, Deposit.State.UPLOADED, Deposit.State.HASHED))):
                    deposit.state=Deposit.State.REPLICATED
                    deposit.save()

        logger.debug(f"forever loop sleeping {SLEEP_TIME} sec before iterating")
        if shutdown.wait(SLEEP_TIME):
            return


def make_or_find_file_node(deposit_file, parent):
    file_node = TreeNode.objects.get(name=deposit_file.name, parent=parent, sha256_sum=deposit_file.sha256_sum)
    if not file_node:
        file_node = TreeNode.objects.create(
            node_type=TreeNode.Type.FILE,
            parent=parent,
            name=deposit_file.name,
            md5_sum=deposit_file.md5_sum,
            sha1_sum=deposit_file.sha1_sum,
            sha256_sum=deposit_file.sha256_sum,
            size=deposit_file.size,
            file_type=deposit_file.type,
            uploaded_at=deposit_file.uploaded_at,
            modified_at=deposit_file.hashed_at
        )
    #todo pre_deposit_modified_at
    #todo uploaded_by

    return file_node


def make_or_find_parent_node(deposit_file):

    organization = Organization.objects.get(id=deposit_file.deposit.organization_id)
    collection = Collection.objects.get(id=deposit_file.deposit.collection_id)

    # Make collection and org tree nodes if non existent
    if organization.tree_node is None:
        org_tree_node = TreeNode.objects.create(
                node_type=TreeNode.Type.ORGANIZATION, name=organization.name
            )
        organization.tree_node = org_tree_node
        organization.save()
    if collection.tree_node is None:
        collection_tree_node = TreeNode.objects.create(
                node_type=TreeNode.Type.COLLECTION, name=collection.name, parent=organization.tree_node
            )
        collection.tree_node = collection_tree_node
        collection.save()

    # filter and ignore empty path segments. Strip file name segment
    parent_segment = collection.tree_node
    for segment in filter(None,deposit_file.relative_path.split("/")[:-1]):
        tree_path_segment = TreeNode.objects.get(parent=parent_segment, name=segment)
        if not tree_path_segment:
            tree_path_segment = TreeNode.objects.create(
                node_type=TreeNode.Type.DIRECTORY, parent=parent_segment, name=segment,
            )
        parent_segment = tree_path_segment

    return parent_segment


def main(argv=None):
    argv = argv or sys.argv
    arg_parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]),
        description="%s - Vault - Process Chunked Files" % (os.path.basename(argv[0])),
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
    logger.addHandler(logging.StreamHandler())
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
