"""Miscellaneous utilities that don't fit anywhere else."""

from datetime import datetime
from datetime import timezone
import functools
import logging
import os.path

from git.repo import Repo
from git.exc import GitError
import pkg_resources

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """Returns a timezone-aware :py:class:`datetime.datetime` representing
    the current instant.

    Helpful for generating current timestamps for inserting into
    timezone-aware database fields.
    """
    return datetime.now(timezone.utc)


@functools.lru_cache
def get_repo_commit_hash() -> str:
    """Returns the full git commit hash for the repository from which
    vault is running.
    """
    vault_dpath = os.path.dirname(__file__)

    try:
        repo = Repo(vault_dpath, search_parent_directories=True)
        return str(repo.commit())
    except GitError as e:
        logger.exception(
            "failed to read vault repo git hash",
            exc_info=e,
        )
        return ""


@functools.lru_cache
def get_vault_version() -> str:
    """Returns the vault version reported in setup.py"""
    try:
        return pkg_resources.get_distribution("vault").version
    except pkg_resources.DistributionNotFound as e:
        logger.exception(
            "failed to read vault package version",
            exc_info=e,
        )
        return ""
