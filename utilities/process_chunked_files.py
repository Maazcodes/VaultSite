# This process handles the files immediately after upload once they are marked as uploaded.
# File chunks are stitched into a single file and piped through hash functions.
# The result is then moved into place and the db row updated.
# Another process will handle the next step in the pipeline.

import argparse
import logging
import os
import shutil
import signal
import sys
import hashlib
import threading
from datetime import datetime
from fs.osfs import OSFS

os.environ["DJANGO_SETTINGS_MODULE"] = "vault_site.settings"
import django

sys.path.append(os.path.join("..", os.getcwd()))
django.setup()
from django.conf import settings
from django.utils import timezone
from vault.models import DepositFile, Deposit, TreeNode, Collection, Organization

SLEEP_TIME = 20
READ_BUFFER_SIZE = 2 * 1024 * 1024
logger = logging.getLogger(__name__)

shutdown = threading.Event()

# Look for hashed files ready for processing.
# Mark Deposit done if all deposit files are done
# TODO trigger on depositfile delete to archive the row
# create tree node
# for now parent is collection
# todo parent will be specified dir in collection maybe
# create chain folder tree nodes saving along the way
# create file tree node, save
# make sure collection has a tree node
# move file into tree


def process_uploaded_deposit_files():

    while True:
        for deposit_file in DepositFile.objects.filter(
            state=DepositFile.State.UPLOADED
        ):
            org_id = deposit_file.deposit.organization_id
            org_tmp_path = str(org_id)

            # Check if we have all chunks for the file. They may be on another node.
            osfs_root = os.path.join(settings.FILE_UPLOAD_TEMP_DIR, org_tmp_path)
            with OSFS(osfs_root) as org_fs:
                org_fs.makedir("/merged", recreate=True)
                chunk_list = []
                try:
                    chunk_list = [
                        c
                        for c in org_fs.filterdir(
                            "/chunks",
                            files=[deposit_file.flow_identifier + "-*.tmp"],
                            namespaces=["details"],
                        )
                        if not c.is_dir
                    ]
                except OSFS.errors.ResourceNotFound as e:
                    logging.warning(f"Error listing files in `/chunks {e}")

                chunk_count = len(chunk_list)

                # If the chunks for this DepositFile are on this machine
                if chunk_count == 0:
                    continue

                combined_chunk_size = sum(
                    org_fs.getsize("/chunks/" + c.name) for c in chunk_list
                )
                logger.info(
                    f"Processing UPLOADED DepositFile {deposit_file.flow_identifier}"
                )

                if combined_chunk_size != deposit_file.size:
                    logger.error(
                        f"Chunk marked as UPLOADED, but sizes don't match: {deposit_file.flow_identifier}"
                    )
                    continue

                merged_filename = deposit_file.flow_identifier + ".merged.tmp"
                md5_hash = hashlib.md5()
                sha1_hash = hashlib.sha1()
                sha256_hash = hashlib.sha256()

                for i in range(1, chunk_count + 1):
                    chunk_filename = (
                        "chunks/" + deposit_file.flow_identifier + "-" + str(i) + ".tmp"
                    )
                    chunk_path = os.path.join(osfs_root, chunk_filename)
                    try:
                        with open(chunk_path, "rb") as f:
                            while True:
                                bytes = f.read(READ_BUFFER_SIZE)
                                if bytes:
                                    org_fs.appendbytes(
                                        "/chunks/" + merged_filename, bytes
                                    )
                                    md5_hash.update(bytes)
                                    sha1_hash.update(bytes)
                                    sha256_hash.update(bytes)
                                else:
                                    break

                    except Exception as e:
                        logger.error(
                            f"Error trying to read chunk file {chunk_filename}"
                        )
                        break
                else:  # if chunk loop did not break
                    deposit_file.md5_sum = md5_hash.hexdigest()
                    deposit_file.sha1_sum = sha1_hash.hexdigest()
                    deposit_file.sha256_sum = sha256_hash.hexdigest()
                    deposit_file.hashed_at = timezone.now()
                    move_into_shafs(
                        deposit_file, org_fs.getospath("/chunks/" + merged_filename)
                    )

                    parent_node = make_or_find_parent_node(deposit_file)
                    file_node, file_node_created = make_or_find_file_node(
                        deposit_file, parent_node
                    )

                    if not file_node_created:
                        # We just replaced the old file, update tree node values to match
                        logger.info(
                            f"TreeNode entry replaced: id:{file_node.id} - {file_node.name}\n"
                            + "\tPrevious data was:"
                        )
                        logger.info(
                            f"\tmd5_sum:{file_node.md5_sum}\n"
                            + f"\tsha1_sum:{file_node.sha1_sum}\n"
                            + f"\tsha256_sum:{file_node.sha256_sum}\n"
                            + f"\tsize:{file_node.size}\n"
                            + f"\tfile_type:{file_node.file_type}\n"
                            + f"\tuploaded_at:{file_node.uploaded_at}\n"
                            + f"\tmodified_at:{file_node.modified_at}\n"
                            + f"\tpre_deposit_modified_at:{file_node.pre_deposit_modified_at}\n"
                            + f"\tuploaded_by:{file_node.uploaded_by}\n"
                        )
                        file_node.md5_sum = deposit_file.md5_sum
                        file_node.sha1_sum = deposit_file.sha1_sum
                        file_node.sha256_sum = deposit_file.sha256_sum
                        file_node.size = deposit_file.size
                        file_node.file_type = deposit_file.type
                        file_node.uploaded_at = deposit_file.uploaded_at
                        file_node.modified_at = deposit_file.hashed_at
                        file_node.pre_deposit_modified_at = (
                            deposit_file.pre_deposit_modified_at
                        )
                        file_node.uploaded_by = deposit_file.deposit.user
                        try:
                            file_node.save()
                        except Exception as e:
                            logger.error(
                                f"Problem saving FileNode {file_node.id} {file_node.name}"
                            )

                    deposit_file.tree_node = file_node
                    deposit_file.state = DepositFile.State.HASHED
                    deposit_file.save()

                    logger.info(
                        f"Chunked file merged {deposit_file.flow_identifier} - {deposit_file.sha256_sum}"
                    )

            # If the Deposit is in the early phase, and no deposit files in early phases
            # todo is is problematic? Should I only check for UPLOADED? We don't want to clobber an upload process
            deposit = deposit_file.deposit
            if deposit.state in (Deposit.State.REGISTERED, Deposit.State.UPLOADED):
                if 0 == len(
                    DepositFile.objects.filter(
                        deposit=deposit,
                        state__in=(
                            DepositFile.State.REGISTERED,
                            DepositFile.State.UPLOADED,
                        ),
                    )
                ):
                    deposit.state = Deposit.State.HASHED
                    deposit.save()
                    deposit.make_deposit_report()

        logger.debug(f"forever loop sleeping {SLEEP_TIME} sec before iterating")
        if shutdown.wait(SLEEP_TIME):
            return


def move_into_shafs(deposit_file, current_file_path):
    shafs_root = get_shafs_folder(deposit_file)
    try:
        os.makedirs(shafs_root, exist_ok=True)
        shutil.move(
            current_file_path,
            os.path.join(shafs_root, deposit_file.sha256_sum),
        )
    except OSError as err:
        logger.error(f"Error moving merged file to destination {shafs_root} - {err}")


# TODO expand this in the future for shafs folder structure
def get_shafs_folder(deposit_file):
    org_id = deposit_file.deposit.organization_id
    org_tmp_path = str(org_id)
    return os.path.join(settings.SHADIR_ROOT, org_tmp_path)


def make_or_find_file_node(deposit_file, parent):
    file_node, created = TreeNode.objects.get_or_create(
        parent=parent,
        name=deposit_file.name,
        defaults=dict(
            node_type=TreeNode.Type.FILE,
            md5_sum=deposit_file.md5_sum,
            sha1_sum=deposit_file.sha1_sum,
            sha256_sum=deposit_file.sha256_sum,
            size=deposit_file.size,
            file_type=deposit_file.type,
            uploaded_at=deposit_file.uploaded_at,
            modified_at=deposit_file.hashed_at,
            pre_deposit_modified_at=deposit_file.pre_deposit_modified_at,
            uploaded_by=deposit_file.deposit.user,
        ),
    )
    msg = "created" if created else "already exists"
    logger.info(f"TreeNode FILE {deposit_file.sha256_sum} {deposit_file.name} {msg}")

    return file_node, created


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
            node_type=TreeNode.Type.COLLECTION,
            name=collection.name,
            parent=organization.tree_node,
        )
        collection.tree_node = collection_tree_node
        collection.save()

    # filter and ignore empty path segments. Strip file name segment
    parent_segment = collection.tree_node
    for segment in filter(None, deposit_file.relative_path.split("/")[:-1]):
        parent_segment, created = TreeNode.objects.get_or_create(
            parent=parent_segment,
            name=segment,
            defaults={"node_type": TreeNode.Type.FOLDER},
        )
        msg = "created" if created else "already exists"
        logger.info(f"TreeNode FOLDER {segment} for {deposit_file.sha256_sum} {msg}")

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

    process_uploaded_deposit_files()


def sig_handler(signum, frame):
    logging.info("shutting down (caught signal %s)", signum)
    shutdown.set()


if __name__ == "__main__":
    main()
