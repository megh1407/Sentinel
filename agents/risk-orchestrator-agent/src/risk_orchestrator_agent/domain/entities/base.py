"""Base entity class shared by every domain entity.

Per the implementation brief, every entity carries: UUID, version, created
timestamp, updated timestamp, correlation ID, trace ID, metadata,
validation, serialization, equality, and hashing. This base class
provides all of that once, so individual entities (`context_entities.py`,
`assessment_entities.py`, `decision_entities.py`) only declare their own
state fields.

Entities are Entities in the DDD sense (Phase 2.5 §1.4): identity
(`entity_id`) persists across attribute changes. Equality/hash are
therefore identity-based here, not structural — this is the one place
this codebase deliberately deviates from `Serializable`'s otherwise
implicit dataclass-default (structural) equality, and it does so
explicitly via `__eq__`/`__hash__` overrides below.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from risk_orchestrator_agent.domain.validators.base import validate_timestamp, validate_uuid
from risk_orchestrator_agent.domain.validators.value_validators import (
    validate_correlation_id,
    validate_created_before_updated,
    validate_metadata,
)
from risk_orchestrator_agent.shared.serialization.serializer import Serializable
from risk_orchestrator_agent.shared.typing.types import JSONDict, Metadata
from risk_orchestrator_agent.shared.utilities.time_utils import new_uuid, utc_now


@dataclasses.dataclass(frozen=False, eq=False)
class Entity(Serializable):
    """Base class for every domain entity (Phase 2.5 §4).

    Entities are intentionally *not* frozen: `context_builder.py` (Phase
    2.2 §5.3) merges updates into an existing entity's fields rather than
    replacing it wholesale. Mutation is confined to designated domain
    services (FRS §4.1's ownership rule) — this base class does not
    itself enforce *who* may call a setter, only provides the
    identity/versioning scaffolding every entity needs.
    """

    entity_id: str = dataclasses.field(default_factory=new_uuid)
    version: int = 1
    created_at: datetime = dataclasses.field(default_factory=utc_now)
    updated_at: datetime = dataclasses.field(default_factory=utc_now)
    correlation_id: str | None = None
    trace_id: str | None = None
    metadata: Metadata = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_uuid(self.entity_id, field_name="entity_id")
        validate_created_before_updated(self.created_at, self.updated_at)
        if self.correlation_id is not None:
            validate_correlation_id(self.correlation_id)
        object.__setattr__(self, "metadata", validate_metadata(self.metadata))

    def touch(self, *, bump_version: bool = True) -> None:
        """Record that this entity was modified: refresh `updated_at`
        and, by default, increment `version` (Phase 2.2 §2's Context
        Versioning responsibility, generalized to every entity).
        """
        self.updated_at = utc_now()
        if bump_version:
            self.version += 1

    def __eq__(self, other: Any) -> bool:
        """Entities are equal iff they share the same identity (Phase
        2.5 §1.4's Entity test) — attribute values are irrelevant.
        """
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.entity_id == other.entity_id

    def __hash__(self) -> int:
        return hash((type(self), self.entity_id))

    def to_dict(self) -> JSONDict:  # noqa: D102 - see Serializable.to_dict
        return super().to_dict()
