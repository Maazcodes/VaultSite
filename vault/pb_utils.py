"""
Contains utilities for interacting with Petabox.
"""

import hashlib
import hmac
import time


class InvalidPetaboxPath(Exception):
    pass


def get_presigned_url(
    pbox_item_slash_filename: str,
    service_name: str,
    petabox_secret: bytes,
    signature_validity_secs: int = 60,
) -> str:
    """
    Builds a presigned, expiring URL for accessing access restricted content in
    petabox. Uses Hank's spec.

    :param pbox_item_slash_filename: item/filename of requested content
    :param service_name: string identifying service requesting the content
    :param petabox_secret: HMAC secret corresponding to *service_name* shared
        with petabox and used to compute URL signature
    :param signature_validity_secs: number of seconds after call-time in which
        resulting URL signature is valid

    :raises InvalidPetaboxPath: when *pbox_item_slash_filename* does not
        describe a path containing both an item and file path

    :seealso: https://webarchive.jira.com/browse/AITFIVE-1764
    :seealso: https://git.archive.org/wb/pygwb/blob/5d8a7c7f65a/gwb/loader/petabox.py#L74
    """
    try:
        [item_id, _] = pbox_item_slash_filename.split("/", maxsplit=1)
    except ValueError as e:
        raise InvalidPetaboxPath(e)

    collapsed_id = item_id.replace(".", "_")
    expiry = int(time.time() + signature_validity_secs)
    msg = f"{collapsed_id}-{expiry}"
    sig = hmac.HMAC(petabox_secret, msg.encode("ascii"), hashlib.md5)
    sig_digest = sig.hexdigest()

    return f"https://archive.org/download/{pbox_item_slash_filename}?{service_name}-{item_id}={expiry}-{sig_digest}"
