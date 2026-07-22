"""Shared type aliases used throughout the Risk Orchestrator domain layer.

These aliases exist purely to make signatures self-documenting. They carry
no behavior and introduce no dependency beyond the standard library, so
`domain/` may import this module without violating the infrastructure-free
rule established in the Project Structure specification (Phase 3.1 §1.3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, MutableMapping, TypeVar

# A JSON-serializable scalar or nested structure. Used as the return/argument
# type for every `to_dict()`/`from_dict()` pair in `shared/serialization`.
JSONPrimitive = str | int | float | bool | None
JSONValue = JSONPrimitive | Mapping[str, "JSONValue"] | list["JSONValue"]
JSONDict = dict[str, JSONValue]

# Metadata bags attached to entities/events are intentionally loosely typed
# (Mapping[str, Any]) because their shape is producer-defined, not something
# the domain layer is entitled to constrain (Phase 2.2 §11's evidence model
# permits arbitrary secondary references).
Metadata = Mapping[str, Any]
MutableMetadata = MutableMapping[str, Any]

# A raw identifier string before it has been wrapped in one of the
# strongly-typed identifier value objects (domain/value_objects/identifiers.py).
RawId = str

# UTC timestamp type used everywhere in this codebase. Never a naive
# datetime — every constructor in this layer enforces tz-awareness
# (see domain/validators/base.py).
UtcDateTime = datetime

T = TypeVar("T")
