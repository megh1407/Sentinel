"""Reusable, composable validators for the domain layer.

Every validator is a plain function that raises `ValidationException`
(never returns a boolean) on failure — consistent with CSEGS §1.1's
"Fail Fast" principle: invalid state is rejected at the boundary, loudly,
never silently absorbed. Value objects (`domain/value_objects`) call
these from `__post_init__`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from risk_orchestrator_agent.domain.exceptions.base import ValidationException
from risk_orchestrator_agent.shared.utilities.time_utils import ensure_utc


def validate_uuid(value: str, *, field_name: str = "id") -> str:
    """Validate that `value` is a syntactically valid UUID string.

    Returns the (unchanged) string on success so this can be used inline:
    `self.worker_id = validate_uuid(worker_id, field_name="worker_id")`.
    """
    if not isinstance(value, str) or not value:
        raise ValidationException(f"{field_name} must be a non-empty string, got {value!r}")
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationException(f"{field_name} is not a valid UUID: {value!r}") from exc
    return value


def validate_non_empty_string(value: str, *, field_name: str) -> str:
    """Validate that `value` is a non-empty, non-whitespace-only string."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationException(f"{field_name} must be a non-empty string, got {value!r}")
    return value


def validate_timestamp(value: datetime, *, field_name: str = "timestamp") -> datetime:
    """Validate and normalize a timestamp to timezone-aware UTC.

    Never accepts a non-`datetime`; a naive datetime is coerced (never
    silently reinterpreted as anything other than UTC).
    """
    if not isinstance(value, datetime):
        raise ValidationException(f"{field_name} must be a datetime, got {type(value).__name__}")
    return ensure_utc(value)


def validate_range(
    value: float,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
) -> float:
    """Validate that `minimum <= value <= maximum`."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationException(f"{field_name} must be numeric, got {type(value).__name__}")
    if not (minimum <= value <= maximum):
        raise ValidationException(
            f"{field_name} must be within [{minimum}, {maximum}], got {value}"
        )
    return float(value)


def validate_int_range(
    value: int,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    """Validate that `minimum <= value <= maximum` for an integer field."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationException(f"{field_name} must be an int, got {type(value).__name__}")
    if not (minimum <= value <= maximum):
        raise ValidationException(
            f"{field_name} must be within [{minimum}, {maximum}], got {value}"
        )
    return value


def validate_non_negative(value: float, *, field_name: str) -> float:
    """Validate that `value >= 0`."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationException(f"{field_name} must be numeric, got {type(value).__name__}")
    if value < 0:
        raise ValidationException(f"{field_name} must be >= 0, got {value}")
    return float(value)


def validate_enum_member(value: object, *, enum_cls: type, field_name: str) -> object:
    """Validate that `value` is a member of `enum_cls` (or its raw value)."""
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid = ", ".join(str(m.value) for m in enum_cls)  # type: ignore[attr-defined]
        raise ValidationException(
            f"{field_name} must be one of [{valid}], got {value!r}"
        ) from exc
