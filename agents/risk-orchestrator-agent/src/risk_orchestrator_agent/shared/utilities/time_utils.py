"""Small, dependency-free helpers shared across the domain layer.

Mirrors Phase 3.1 §2's `utils/time_utils.py` placement — kept here under
`shared/utilities` per this implementation phase's directory layout. Contains
no business logic, only mechanical helpers (current time, id generation).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current instant as a timezone-aware UTC datetime.

    Every timestamp field in this domain layer is produced via this
    function so that "naive vs. aware" datetime bugs cannot occur.
    """
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Generate a new random UUID4 string.

    Used for `entity_id`/`event_id` generation where the caller does not
    supply one explicitly (e.g., first construction of a new aggregate).
    """
    return str(uuid.uuid4())


def ensure_utc(value: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC.

    Naive datetimes are assumed to already represent UTC (never silently
    reinterpreted as local time) and are stamped accordingly; aware
    datetimes are converted. This is a defensive normalization helper,
    not a validator — validators (domain/validators) are what reject bad
    input outright.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
