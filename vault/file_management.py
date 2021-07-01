import sys
import os
import logging
import unicodedata
import re
from vault import models

logger = logging.getLogger(__name__)

def create_or_update_file(request, attribs):
    collection_id = attribs.get('collection', None)
    if collection_id:
        collection = models.Collection.objects.get(pk=collection_id)

        models.File.objects.update_or_create(
            collection       = collection,
            client_filename  = attribs['name'],
            staging_filename = attribs['staging_filename'],
            md5_sum          = attribs['md5sumV'],
            sha1_sum         = attribs['sha1sumV'],
            sha256_sum       = attribs['sha256sumV'],
            defaults = {
                       'size': attribs['sizeV'],
                  'file_type': attribs.get('file_type', None),
                'uploaded_by': request.user,
                    'comment': attribs.get('comment', ""),
            }
        )
    else:
        messages.error(request, 'ERROR: Invalid Request.')


def generateHashes(filename):
    hashes = dict()
    import hashlib
    md5_hash    = hashlib.md5()
    sha1_hash   = hashlib.sha1()
    sha256_hash = hashlib.sha256()
    with open(filename,"rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
            sha1_hash.update(byte_block)
            sha256_hash.update(byte_block)
    f.close()
    hashes['md5']    =    md5_hash.hexdigest()
    hashes['sha1']   =   sha1_hash.hexdigest()
    hashes['sha256'] = sha256_hash.hexdigest()
    return hashes


def clean_spaces(s):
    s = s.replace('\r', '')
    s = s.replace('\t', ' ')
    s = s.replace('\f', ' ')
    return s


def unicode_to_ascii(u):
    a = unicodedata.normalize('NFD', u)
    a.encode('ascii', 'ignore').decode('ascii')
    return a


def posix_string(s):
    p = clean_spaces(s)
    p = unicode_to_ascii(p)
    p = re.sub('[^a-zA-Z0-9_\-\.]', '_', p)
    return p


def posix_path(s):
    p = clean_spaces(s)
    p = unicode_to_ascii(p)
    p = re.sub('[^a-zA-Z0-9_\-\/\.]', '_', p)
    p = os.path.normpath(p)
    return p


def db_file_update(fname, bakname):
    from django.http import HttpResponse
    from django.db import transaction

    class dbFileUpdateError(Exception):
        pass

    f = models.File.objects.select_for_update().filter(
            staging_filename=fname,
            )
    if f.count()   == 0:
        pass
    elif f.count() == 1:
        with transaction.atomic():
            try:
                f[0].staging_filename = bakname
                f[0].save()
                logger.info(f"staging_filename updated from {fname} to {bakname}")
            except Exception as e:
                logger.error(f"While handling {bakname} : {e}")
    else:
        err = f"db_file_update: {f.count()} db rows matched {fname}"
        logger.error(err)
        raise dbFileUpdateError(err)


def file_backup(fname):
    if os.path.isfile(fname):
        i = 1
        bakname = fname
        while os.path.isfile(bakname):
            bakname = fname + '.~' + str(i) + '~'
            i += 1
        os.rename(fname, bakname)
        db_file_update(fname, bakname)
        logger.info(f"moved {fname} to {bakname}")


def move_temp_file(request, attribs):
    import filetype
    from pathlib import Path
    from sanitize_filename import sanitize
    from django.conf import settings

    root = settings.MEDIA_ROOT

    temp_file = attribs['tempfile']
    ftype     = filetype.guess(temp_file)
    if ftype:
        attribs['file_type'] = ftype.mime
    else:
        attribs['file_type'] = ''
    org         = Path(posix_string(attribs['orgname']))
    coll        = Path(posix_string(attribs['collname']))
    filepath    = Path(attribs['name'])
    filepath    = os.path.normpath(filepath)

    fname       = os.path.basename(filepath)
    fname       = sanitize(fname)

    userdir     = os.path.dirname(filepath)
    target_path = os.path.join(root, org, coll, userdir)

    Path(target_path).mkdir(parents=True, exist_ok=True)

    target_file = os.path.join(target_path, fname)
    attribs['staging_filename'] = target_file

    # Move the file on the filesystem, if necessary
    file_backup(target_file)
    os.rename(temp_file.encode('U8'), target_file.encode('U8'))
    create_or_update_file(request, attribs)

