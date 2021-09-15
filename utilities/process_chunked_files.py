# This process handles the files immediately after upload once they are marked as uploaded.
# File chunks are stitched into a single file and piped through hash functions.
# The result is then moved into place and the db row updated.
# Another process will handle the next step in the pipeline.

import argparse
import logging
import os
import signal
import sys
import hashlib
import threading
from fs.osfs import OSFS

os.environ['DJANGO_SETTINGS_MODULE'] = 'vault_site.settings'
import django

sys.path.append(os.path.join("..",os.getcwd()))
django.setup()
from django.conf import settings
from vault.models import DepositFile

SLEEP_TIME = 20
logger = logging.getLogger(__name__)

shutdown = threading.Event()


def process_uploaded_deposit_files():

    while True:
        for deposit_file in DepositFile.objects.filter(state=DepositFile.State.UPLOADED):
            org_id = deposit_file.deposit.organization_id
            org_tmp_path = str(org_id)

            # Check if we have all chunks for the file. They may be on another node.
            with OSFS(
                    os.path.join(settings.FILE_UPLOAD_TEMP_DIR, org_tmp_path)
            ) as org_fs:
                org_fs.makedir("/merged", recreate=True)
                chunk_list = [c for c in org_fs.filterdir("/chunks",
                                                          files=[deposit_file.flow_identifier + "-*.tmp"],
                                                          namespaces=['details']) if not c.is_dir]
                chunk_count = len(chunk_list)

                # If the chunks for this DepositFile are on this machine
                if chunk_count > 0:
                    combined_chunk_size = sum(org_fs.getsize("/chunks/" + c.name) for c in chunk_list)
                    logger.info(f"Processing UPLOADED DepositFile {deposit_file.flow_identifier}")

                    if combined_chunk_size == deposit_file.size:
                        merged_filename = deposit_file.flow_identifier + ".merged.tmp"
                        md5_hash = hashlib.md5()
                        sha1_hash = hashlib.sha1()
                        sha256_hash = hashlib.sha256()
                        # TODO read full chunk, or should we read bytes instead?
                        for i in range(1, chunk_count + 1):
                            chunk_bytes = org_fs.readbytes(
                                "/chunks/" + deposit_file.flow_identifier + "-" + str(i) + ".tmp")
                            org_fs.appendbytes("/chunks/" + merged_filename, chunk_bytes)
                            md5_hash.update(chunk_bytes)
                            sha1_hash.update(chunk_bytes)
                            sha256_hash.update(chunk_bytes)

                        org_fs.move("/chunks/" + merged_filename, "/merged/" + deposit_file.flow_identifier + ".merged",
                                    overwrite=True)
                        deposit_file.md5_sum = md5_hash.hexdigest()
                        deposit_file.sha1_sum = sha1_hash.hexdigest()
                        deposit_file.sha256_sum = sha256_hash.hexdigest()
                        deposit_file.state = DepositFile.State.HASHED
                        deposit_file.save()
                        logger.info(f"Chunked file merged {deposit_file.flow_identifier} - {deposit_file.sha256_sum}")

                    else:
                        logger.error(f"Chunk marked as UPLOADED, but sizes don't match: {deposit_file.flow_identifier}")

        logger.debug(
            f"forever loop sleeping {SLEEP_TIME} sec before iterating")
        if shutdown.wait(SLEEP_TIME):
            return


def main(argv=None):
    argv = argv or sys.argv
    arg_parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]),
        description='%s - Vault - Process Chunked Files' % (
            os.path.basename(argv[0])),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    arg_parser.add_argument(
        '-v', '--verbose', dest='log_level', action='store_const',
        default=logging.INFO, const=logging.DEBUG, help='verbose logging')
    args = arg_parser.parse_args(args=sys.argv[1:])

    logging.root.setLevel(level=args.log_level)
    logger.addHandler(logging.StreamHandler())
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGHUP, sig_handler)
    signal.signal(signal.SIGQUIT, sig_handler)

    process_uploaded_deposit_files()


def sig_handler(signum, frame):
    logging.info('shutting down (caught signal %s)', signum)
    shutdown.set()


if __name__ == "__main__":
    main()
