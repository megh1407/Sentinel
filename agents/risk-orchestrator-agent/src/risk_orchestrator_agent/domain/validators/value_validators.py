"""Domain-specific validators, composed from `domain/validators/base.py`.

These are the named validators explicitly requested by the implementation
brief (UUID, Timestamp, Probability, Risk Score, Coordinate, Metadata,
Version, Correlation) — each wraps a base primitive with the specific
bounds/semantics the corresponding value object needs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from risk_orchestrator_agent.domain.constants.limits import (
    MAX_RISK_SCORE,
    MAX_UNIT_INTERVAL,
    MIN_RISK_SCORE,
    MIN_UNIT_INTERVAL,
)
from risk_orchestrator_agent.domain.exceptions.base import ValidationException
from risk_orchestrator_agent.domain.validators.base import (
    validate_int_range,
    validate_non_empty_string,
    validate_range,
    validate_timestamp,
    validate_uuid,
)


def validate_probability(value: float, *, field_name: str = "probability") -> float:
    """Validate a probability/confidence/strength value lies in [0, 1]."""
    return validate_range(
        value, field_name=field_name, minimum=MIN_UNIT_INTERVAL, maximum=MAX_UNIT_INTERVAL
    )


def validate_risk_score(value: int, *, field_name: str = "score") -> int:
    """Validate a raw risk score lies in [0, 100] (Phase 2.1 §3.5)."""
    return validate_int_range(
        value, field_name=field_name, minimum=MIN_RISK_SCORE, maximum=MAX_RISK_SCORE
    )


def validate_coordinate(latitude: float, longitude: float) -> tuple[float, float]:
    """Validate a (latitude, longitude) pair lies within physically valid bounds."""
    lat = validate_range(latitude, field_name="latitude", minimum=-90.0, maximum=90.0)
    lon = validate_range(longitude, field_name="longitude", minimum=-180.0, maximum=180.0)
    return lat, lon


def validate_metadata(value: Mapping[str, object] | None) -> Mapping[str, object]:
    """Validate a metadata mapping is genuinely a mapping (never a list/str
    passed in error) and return an immutable-friendly copy.
    """
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValidationException(f"metadata must be a mapping, got {type(value).__name__}")
    return dict(value)


def validate_version(value: str, *, field_name: str = "version") -> str:
    """Validate a semantic-version-shaped string (`MAJOR.MINOR.PATCH`).

    Deliberately lenient (does not enforce full SemVer pre-release/build
    metadata grammar) — this codebase only needs to distinguish "looks
    like a version" from "obviously not," per CSEGS §9.2's config-schema
    validation being the authoritative gate, not this helper.
    """
    text = validate_non_empty_string(value, field_name=field_name)
    parts = text.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValidationException(
            f"{field_name} must be a MAJOR.MINOR.PATCH version string, got {value!r}"
        )
    return text


def validate_correlation_id(value: str, *, field_name: str = "correlation_id") -> str:
    """Validate a `correlation_id`/`causation_id`/`trace_id`-shaped value.

    These are UUIDs by platform convention (Phase 1 §4) but are validated
    as a distinct named validator per the implementation brief, so a
    future relaxation of the format (e.g., a vendor trace-id format) can
    change in exactly one place.
    """
    return validate_uuid(value, field_name=field_name)


def validate_created_before_updated(
    created_at: datetime, updated_at: datetime
) -> tuple[datetime, datetime]:
    """Validate that an entity's `updated_at` never precedes its `created_at`."""
    created = validate_timestamp(created_at, field_name="created_at")
    updated = validate_timestamp(updated_at, field_name="updated_at")
    if updated < created:
        raise ValidationException(
            f"updated_at ({updated.isoformat()}) precedes created_at ({created.isoformat()})"
        )
    return created, updated
