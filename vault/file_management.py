import hashlib
import logging
import os
import re
import unicodedata
from pathlib import Path

from sanitize_filename import sanitize
from django.conf import settings
import filetype

from vault import models

# from sentry_sdk import capture_exception, capture_message

logger = logging.getLogger(__name__)


def create_or_update_file(request, attribs):
    collection_id = attribs.get("collection", None)
    if collection_id:
        collection = models.Collection.objects.get(pk=collection_id)

        models.File.objects.update_or_create(
            collection=collection,
            client_filename=attribs["name"],
            staging_filename=attribs["staging_filename"],
            md5_sum=attribs["md5sumV"],
            sha1_sum=attribs["sha1sumV"],
            sha256_sum=attribs["sha256sumV"],
            defaults={
                "size": attribs["sizeV"],
                "file_type": attribs.get("file_type", None),
                "uploaded_by": request.user,
                "comment": attribs.get("comment", ""),
            },
        )
    else:
        # messages.error(request, 'ERROR: Invalid Request.')
        pass


def generate_hashes(filename):
    hashes = {}

    md5_hash = hashlib.md5()
    sha1_hash = hashlib.sha1()
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as file:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: file.read(4096), b""):
            md5_hash.update(byte_block)
            sha1_hash.update(byte_block)
            sha256_hash.update(byte_block)
    file.close()
    hashes["md5"] = md5_hash.hexdigest()
    hashes["sha1"] = sha1_hash.hexdigest()
    hashes["sha256"] = sha256_hash.hexdigest()
    return hashes


def clean_spaces(in_str):
    in_str = in_str.replace("\r", "")
    in_str = in_str.replace("\t", " ")
    in_str = in_str.replace("\f", " ")
    return in_str


def unicode_to_ascii(in_str):
    out_str = unicodedata.normalize("NFD", in_str)
    out_str.encode("ascii", "ignore").decode("ascii")
    return out_str


def posix_string(in_str):
    out_str = clean_spaces(in_str)
    out_str = unicode_to_ascii(out_str)
    out_str = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", out_str)
    return out_str


def posix_path(in_str):
    out_str = clean_spaces(in_str)
    out_str = unicode_to_ascii(out_str)
    out_str = re.sub(r"[^a-zA-Z0-9_\-\/\.]", "_", out_str)
    out_str = os.path.normpath(out_str)
    return out_str


def hash_to_idx_list(shasum):
    # Decompose 64 hex-digits of sha256 hash into 32 pairs of indices
    i = 0
    dirlevels = []
    while i < 64:
        dirlevels.append(shasum[i : i + 2])
        i = i + 2
    return dirlevels


def calculate_sha_file_path(fname, shasum):
    class CalculateShaFilePathError(Exception):
        pass

    dirlvls = hash_to_idx_list(shasum)

    # Calculate file path
    shapath = Path(settings.SHADIR_ROOT)
    shafile = shapath
    if os.path.isfile(fname):
        while os.path.isdir(shapath):
            shapath = os.path.join(shapath, dirlvls.pop(0))
        shafile = os.path.join(shapath, shasum)
    else:
        err = f"File not found: {fname} ({shasum})"
        logger.error(err)
        raise CalculateShaFilePathError(err)
    return shafile


def metavirtual_linker(fname):
    class MetaVirtualLinkerError(Exception):
        pass

    try:
        file = models.File.objects.get(staging_filename=fname)
    except models.File.DoesNotExist as e:
        err = f"File not found in database: {fname}"
        logger.error(err)
        raise MetaVirtualLinkerError(err) from e
    except models.File.MultipleObjectsReturned as e:
        err = f"Multiple db rows matched: {fname}"
        logger.error(err)
        raise MetaVirtualLinkerError(err) from e
    except Exception as e:  # pylint: disable=broad-except
        logger.error("While handling %s : %s", fname, e)

    shasum = file.sha256_sum
    shafile = calculate_sha_file_path(fname, shasum)

    if os.path.isfile(shafile):
        logger.info(
            "metavirtual_linker: linkage already exists - DEDUP! %s => %s",
            fname,
            shafile,
        )
    else:
        # Here is where we mv fname to shafile and ???
        logger.info("metavirtual_linker: linkage needed - %s => %s", fname, shafile)


def db_file_update(fname, bakname):
    class DBFileUpdateError(Exception):
        pass

    try:
        file = models.File.objects.get(staging_filename=fname)
        file.staging_filename = bakname
        file.save()
        logger.info("staging_filename updated from %s to %s", fname, bakname)
    except models.File.DoesNotExist:
        pass
    except models.File.MultipleObjectsReturned as e:
        err = f"db_file_update: multiple db rows matched {fname}"
        logger.error(err)
        raise DBFileUpdateError(err) from e
    except Exception as e:  # pylint: disable=broad-except
        # capture_exception(e)
        logger.error("While handling %s : %s", bakname, e)


def file_backup(fname):
    class FileBackupError(Exception):
        pass

    if os.path.isfile(fname):
        i = 1
        bakname = fname
        while os.path.isfile(bakname):
            bakname = fname + ".~" + str(i) + "~"
            i += 1
        os.rename(fname, bakname)
        db_file_update(fname, bakname)
        logger.info("moved %s to %s", fname, bakname)
    elif os.path.isfile(fname + ".~1~"):
        err = f"File {fname} does NOT exist, BUT bakfile DOES!"
        logger.error(err)
        raise FileBackupError(err)
    else:
        pass


def move_temp_file(request, attribs):
    root = settings.MEDIA_ROOT

    temp_file = attribs["tempfile"]
    ftype = filetype.guess(temp_file)
    if ftype:
        attribs["file_type"] = ftype.mime
    else:
        attribs["file_type"] = ""
    org = Path(posix_string(attribs["orgname"]))
    coll = Path(posix_string(attribs["collname"]))
    filepath = Path(attribs["name"])
    filepath = os.path.normpath(filepath)

    fname = os.path.basename(filepath)
    fname = sanitize(fname)

    userdir = os.path.dirname(filepath)
    target_path = os.path.join(root, org, coll, userdir)

    Path(target_path).mkdir(parents=True, exist_ok=True)

    target_file = os.path.join(target_path, fname)
    attribs["staging_filename"] = target_file

    # Move the file on the filesystem, if necessary
    file_backup(target_file)
    os.rename(temp_file.encode("U8"), target_file.encode("U8"))
    create_or_update_file(request, attribs)
    metavirtual_linker(target_file)
