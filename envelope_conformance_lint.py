"""
envelope_conformance_lint.py

Diffs every event schema's envelope fields against contracts/common/BaseEvent.avsc.

This is the tool BaseEvent.avsc's own doc string has claimed exists since before
this artifact ("...enforced by a codegen lint that diffs every event schema's
envelope fields against this definition."). It did not, in fact, exist -- see
Artifact 10 (Validation & Compliance Architecture), Founding Evidence, and
Artifact 3 Principle V ("Governance Must Be Mechanical, Never Just Documented").
Built per Artifact 12 (Migration Plan), Phase 0: "Build the narrowest CI subset
first -- Avro syntax and envelope-conformance checking -- against the contract
tree as it currently stands, before any cleanup begins."

Scope (deliberately narrow -- matches Phase 0, not the full Artifact 10 Phase 1
pre-merge gate, which is built incrementally later):

  1. Every field declared on BaseEvent (contracts/common/BaseEvent.avsc) must be
     present, by name, on every event schema (contracts/events/{Name}/{version}/
     schema.avsc), with an identical `type`.
  2. Those fields must appear in the same relative order as they do on BaseEvent.
     Non-BaseEvent fields (e.g. the `zone_id` field every current event schema
     inserts between `site_id` and `partition_key`) may be interspersed --
     that's an existing, universal, intentional per-domain addition, not an
     envelope violation, and this lint does not police it.
  3. Where an event schema supplies a `default` for `event_type`, it must equal
     the schema's own record `name` -- BaseEvent.avsc's own doc for that field
     states "Must match the schema subject name."

Deliberately NOT checked here (out of scope for this tool):
  - Decision-metadata field naming (`explanation` vs. `justification`). Artifact
    6 Section 2 explicitly tracks ActionRequest's `justification` field as a
    known, deferred, planned breaking-change rename -- not a defect this lint
    should flag. That's `naming_lint.py`'s job (Artifact 10 Section 2), not yet
    built.
  - Payload shape, category declaration, causation-chain plausibility, or any
    other Phase 1 pre-merge check listed in Artifact 10 -- each is its own,
    separately-built tool, added incrementally.

Comparison is performed against the raw (unexpanded) Avro JSON, field by field,
rather than fastavro's fully-resolved schema -- BaseEvent's own field `type`
values (e.g. `"com.sentinel.common.Metadata"` by name, or the UUID/timestamp
logicalType structures) are copied verbatim into every event schema today, so a
raw structural diff is both sufficient and avoids masking a real divergence
behind schema-resolution.
"""
from __future__ import annotations

import json
from pathlib import Path

from schema_loader import CONTRACTS_ROOT, COMMON_DIR, EVENTS_DIR, list_event_schemas

BASE_EVENT_PATH = COMMON_DIR / "BaseEvent.avsc"


class EnvelopeViolation(Exception):
    """Raised for one specific, named envelope-conformance failure."""


def _load_base_event_fields() -> list[dict]:
    with open(BASE_EVENT_PATH) as f:
        raw = json.load(f)
    return raw["fields"]


def _load_event_fields(event_name: str, version: str) -> tuple[dict, list[dict]]:
    path = EVENTS_DIR / event_name / version / "schema.avsc"
    with open(path) as f:
        raw = json.load(f)
    return raw, raw["fields"]


def check_envelope_conformance(event_name: str, version: str, base_fields: list[dict]) -> list[str]:
    """Returns a list of violation messages for one event schema (empty = conformant)."""
    violations: list[str] = []
    raw, event_fields = _load_event_fields(event_name, version)

    event_field_by_name = {}
    event_field_index = {}
    for idx, field in enumerate(event_fields):
        # Only the first occurrence of a name is meaningful for envelope purposes.
        if field["name"] not in event_field_by_name:
            event_field_by_name[field["name"]] = field
            event_field_index[field["name"]] = idx

    # 1 & 2: presence, type equality, and relative order.
    last_index_seen = -1
    for base_field in base_fields:
        name = base_field["name"]
        if name not in event_field_by_name:
            violations.append(f"missing envelope field '{name}' (declared on BaseEvent)")
            continue

        actual = event_field_by_name[name]
        if actual["type"] != base_field["type"]:
            violations.append(
                f"envelope field '{name}' type mismatch: "
                f"BaseEvent declares {base_field['type']!r}, "
                f"schema declares {actual['type']!r}"
            )

        idx = event_field_index[name]
        if idx < last_index_seen:
            violations.append(
                f"envelope field '{name}' is out of order relative to other BaseEvent fields"
            )
        else:
            last_index_seen = idx

    # 3: event_type default, where present, must match the record's own name.
    event_type_field = event_field_by_name.get("event_type")
    if event_type_field is not None and "default" in event_type_field:
        declared_default = event_type_field["default"]
        record_name = raw.get("name")
        if declared_default != record_name:
            violations.append(
                f"'event_type' default {declared_default!r} does not match "
                f"the schema's own record name {record_name!r} "
                f"(BaseEvent.avsc: \"Must match the schema subject name.\")"
            )

    return violations


def main() -> None:
    base_fields = _load_base_event_fields()
    all_violations: dict[str, list[str]] = {}

    for event_name, version in list_event_schemas():
        violations = check_envelope_conformance(event_name, version, base_fields)
        label = f"{event_name}/{version}"
        if violations:
            all_violations[label] = violations
            print(f"FAIL {label}")
            for v in violations:
                print(f"       - {v}")
        else:
            print(f"OK   {label}")

    if all_violations:
        total = sum(len(v) for v in all_violations.values())
        raise SystemExit(
            f"{len(all_violations)} schema(s), {total} envelope-conformance violation(s)"
        )


if __name__ == "__main__":
    main()
