"""Miscellaneous utilities that don't fit anywhere else."""

from datetime import datetime
from datetime import timezone


def utcnow() -> datetime:
    """Returns a timezone-aware :py:class:`datetime.datetime` representing
    the current instant.

    Helpful for generating current timestamps for inserting into
    timezone-aware database fields.
    """
    return datetime.now(timezone.utc)
