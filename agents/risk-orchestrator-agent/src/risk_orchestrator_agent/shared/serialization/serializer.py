"""Reusable serialization framework for the domain layer.

Every entity, value object, event, command, and response DTO in this
codebase is a `frozen=True` (or, for entities, mutable-but-controlled)
dataclass that mixes in `Serializable`. This is the single place
`to_dict`/`from_dict`/`to_json`/`from_json`/deep-copy logic lives, so
individual domain classes never hand-roll their own (Coding Standards
§1.1's DRY principle, applied specifically to serialization).

No third-party dependency is required — this uses only `dataclasses` and
`json` from the standard library, keeping the domain layer framework-free
per Phase 2.5 §1.3.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import json
import typing
from datetime import date, datetime
from typing import Any, ClassVar, TypeVar, Union, get_args, get_origin

from risk_orchestrator_agent.shared.typing.types import JSONDict, JSONValue

T = TypeVar("T", bound="Serializable")


def _encode_value(value: Any) -> JSONValue:
    """Recursively encode a Python value into a JSON-safe structure."""
    if isinstance(value, enum.Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Serializable):
        return value.to_dict()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _encode_value(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _encode_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_encode_value(v) for v in value]
    # Fallback: best-effort string representation rather than a hard
    # failure — a domain object should never fail to serialize outright,
    # consistent with the platform-wide "degrade, never fabricate, never
    # crash the cycle" philosophy (Phase 2.1 §10.2) applied here to
    # observability/debug serialization rather than scoring correctness.
    return str(value)


def _unwrap_optional(field_type: Any) -> Any:
    """If `field_type` is `X | None` (or `Optional[X]`), return `X`."""
    if get_origin(field_type) is Union:
        args = [a for a in get_args(field_type) if a is not type(None)]  # noqa: E721
        if len(args) == 1:
            return args[0]
    return field_type


def _decode_value(value: Any, field_type: Any) -> Any:
    """Recursively reconstruct `value` according to the declared `field_type`.

    This is what makes `from_dict(to_dict(x)) == x` true for datetimes,
    enums, and nested `Serializable` objects/collections — a plain
    `cls(**payload)` is not sufficient once any field is not a bare
    JSON primitive.
    """
    if value is None:
        return None

    field_type = _unwrap_optional(field_type)
    origin = get_origin(field_type)

    # Nested Serializable (entity/value-object/event field)
    if isinstance(field_type, type) and issubclass(field_type, Serializable):
        if isinstance(value, dict):
            return field_type.from_dict(value)
        return value

    # Enum field
    if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
        return field_type(value)

    # datetime field
    if isinstance(field_type, type) and issubclass(field_type, datetime):
        return datetime.fromisoformat(value) if isinstance(value, str) else value

    # tuple[...]/list[...] of a decodable type
    if origin in (tuple, list) and isinstance(value, (list, tuple)):
        args = get_args(field_type)
        inner_type = args[0] if args else None
        decoded = [
            _decode_value(item, inner_type) if inner_type is not None else item
            for item in value
        ]
        return tuple(decoded) if origin is tuple else decoded

    # dict[...] of a decodable value type
    if origin is dict and isinstance(value, dict):
        args = get_args(field_type)
        value_type = args[1] if len(args) == 2 else None
        if value_type is not None:
            return {k: _decode_value(v, value_type) for k, v in value.items()}
        return value

    return value


class SchemaVersionMismatchError(ValueError):
    """Raised when `from_dict` receives a payload whose `schema_version`
    is incompatible with the target class's declared version and no
    migration path (`_migrate`) is registered to bridge the gap.
    """


class Serializable:
    """Mixin providing versioned, recursive (de)serialization.

    Subclasses are expected to be `@dataclass`-decorated (either frozen,
    for value objects/events/DTOs, or mutable, for entities). This class
    is deliberately *not* itself a dataclass — dataclass inheritance
    requires every class in the chain to agree on `frozen`, and this
    mixin must support both frozen and mutable subclasses, so it declares
    no fields and no `@dataclass` decorator at all.
    """

    #: Bumped whenever this class's shape changes in a way a consumer
    #: must know about (Phase 1 §4.10's BACKWARD-compatibility policy,
    #: applied at the domain-object level rather than only the wire level).
    schema_version: ClassVar[int] = 1

    def to_dict(self) -> JSONDict:
        """Serialize this object to a plain, JSON-safe dictionary.

        The result always carries `schema_version` so a later
        `from_dict` call (potentially against a newer class definition)
        can detect and, where supported, migrate an older payload.
        """
        data: JSONDict = {}
        for field in dataclasses.fields(self):
            data[field.name] = _encode_value(getattr(self, field.name))
        data["schema_version"] = self.schema_version
        return data

    def to_json(self) -> str:
        """Serialize this object to a JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @classmethod
    def _migrate(cls: type[T], payload: JSONDict, from_version: int) -> JSONDict:
        """Hook for subclasses to bridge an older `schema_version` payload
        forward to the class's current shape. The default implementation
        performs no migration — a subclass introducing a breaking change
        must override this and is expected to document the migration
        (Coding Standards §14.1's ADR requirement).
        """
        return payload

    @classmethod
    def from_dict(cls: type[T], payload: JSONDict) -> T:
        """Reconstruct an instance from a dictionary produced by `to_dict`.

        Unknown/extra keys are dropped rather than rejected (forward
        compatibility, Phase 1 §4.10) as long as every required field for
        this class is present after any migration step runs.
        """
        payload = dict(payload)
        incoming_version = int(payload.pop("schema_version", cls.schema_version))
        if incoming_version != cls.schema_version:
            if cls._migrate.__func__ is Serializable._migrate.__func__:
                # No subclass migration path registered — this is the
                # common case (most classes never change shape) and,
                # per this method's contract, an unbridgeable mismatch.
                raise SchemaVersionMismatchError(
                    f"{cls.__name__}: payload schema_version {incoming_version} does not match "
                    f"this build's {cls.schema_version} and no migration is defined."
                )
            payload = cls._migrate(payload, incoming_version)
        payload.pop("schema_version", None)

        known_fields = {f.name for f in dataclasses.fields(cls)}
        try:
            type_hints = typing.get_type_hints(cls)
        except Exception:  # pragma: no cover - defensive; fall back to raw values
            type_hints = {}
        filtered = {
            k: _decode_value(v, type_hints.get(k)) for k, v in payload.items() if k in known_fields
        }
        return cls(**filtered)  # type: ignore[call-arg]

    @classmethod
    def from_json(cls: type[T], raw: str) -> T:
        """Reconstruct an instance from a JSON string produced by `to_json`."""
        return cls.from_dict(json.loads(raw))

    def deep_copy(self: T) -> T:
        """Return a fully independent deep copy of this object.

        Required for the immutability guarantees in Phase 2.5 §5.1 —
        handing out a reference to an existing immutable value object is
        safe by construction, but callers that need a detached working
        copy (e.g., a simulation seed, Phase 2.5 §13) use this explicitly
        rather than mutating the shared instance.
        """
        return copy.deepcopy(self)
