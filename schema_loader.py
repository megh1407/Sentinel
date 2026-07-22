"""
schema_loader.py

Resolves SENTINEL's cross-file Avro named-type references (contracts/common/*.avsc
referenced by name from contracts/events/*/v*/schema.avsc) using fastavro's
named-schema cache. This mirrors how the Confluent Schema Registry's "schema
references" feature works in production: common types are registered once as
their own subjects, and event schemas reference them by fully-qualified name.
This module is the single place that encodes the correct load order --
nothing else in the codebase should hand-roll Avro parsing.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastavro.schema import parse_schema, load_schema_ordered

CONTRACTS_ROOT = Path(__file__).resolve().parent / "contracts"
COMMON_DIR = CONTRACTS_ROOT / "common"
EVENTS_DIR = CONTRACTS_ROOT / "events"
AGENT_CONTRACTS_DIR = CONTRACTS_ROOT / "agent-contracts"

# Explicit dependency order for common/*.avsc. New common types MUST be added
# here in dependency order (a type that references another must come after
# it) -- this list is intentionally hand-maintained rather than
# auto-topologically-sorted, so a circular or forward reference is caught by
# a loud KeyError at load time rather than silently "working" via accidental
# dict ordering.
COMMON_SCHEMA_ORDER: list[str] = [
    "enums/Environment.avsc",
    "Metadata.avsc",
    "GeoLocation.avsc",
    "EvidenceItem.avsc",
    "RiskContributor.avsc",
    "enums/ConfidenceDerivation.avsc",
    "ConfidenceScore.avsc",
    "ExplanationObject.avsc",
    "BaseEvent.avsc",
]


def load_common_named_schemas() -> dict:
    """Parses every common/*.avsc in dependency order, accumulating a
    fastavro named_schemas cache that subsequent event-schema parses can
    reference by fully-qualified name (e.g. 'com.sentinel.common.Metadata')."""
    named_schemas: dict = {}
    for filename in COMMON_SCHEMA_ORDER:
        path = COMMON_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Common schema '{filename}' listed in COMMON_SCHEMA_ORDER but not found at {path}"
            )
        with open(path) as f:
            raw = json.load(f)
        parse_schema(raw, named_schemas=named_schemas)
    return named_schemas


def load_event_schema(event_name: str, version: str = "v1") -> dict:
    """Loads and fully resolves one event schema (contracts/events/<Name>/<version>/schema.avsc),
    pre-seeding the common named-type cache first. Returns the fully-resolved
    (expanded) fastavro schema dict, suitable for direct use in serialization,
    validation, and codegen."""
    named_schemas = load_common_named_schemas()
    path = EVENTS_DIR / event_name / version / "schema.avsc"
    if not path.exists():
        raise FileNotFoundError(f"Event schema not found: {path}")
    with open(path) as f:
        raw = json.load(f)
    return parse_schema(raw, named_schemas=named_schemas)


def load_agent_contract_schema(type_name: str, version: str = "v1") -> dict:
    """Loads and fully resolves one agent-contract Avro record
    (contracts/agent-contracts/<version>/<TypeName>.avsc), pre-seeding the
    common named-type cache first. Mirrors load_event_schema -- agent
    contracts are events (Artifact 7 §1, §12) transported identically, they
    are simply laid out under agent-contracts/ rather than events/<Name>/v*/."""
    named_schemas = load_common_named_schemas()
    path = AGENT_CONTRACTS_DIR / version / f"{type_name}.avsc"
    if not path.exists():
        raise FileNotFoundError(f"Agent-contract schema not found: {path}")
    with open(path) as f:
        raw = json.load(f)
    return parse_schema(raw, named_schemas=named_schemas)


def list_agent_contract_schemas() -> list[tuple[str, str]]:
    """Returns (type_name, version) pairs for every *.avsc discovered under
    contracts/agent-contracts/, mirroring list_event_schemas."""
    results = []
    if not AGENT_CONTRACTS_DIR.exists():
        return results
    for version_dir in sorted(AGENT_CONTRACTS_DIR.iterdir()):
        if not version_dir.is_dir():
            continue
        for schema_path in sorted(version_dir.glob("*.avsc")):
            results.append((schema_path.stem, version_dir.name))
    return results


def list_event_schemas() -> list[tuple[str, str]]:
    """Returns (event_name, version) pairs for every schema.avsc under contracts/events/,
    discovered from disk rather than hand-maintained, so a new event schema is
    automatically picked up by codegen/tests without an extra registration step."""
    results = []
    for event_dir in sorted(EVENTS_DIR.iterdir()):
        if not event_dir.is_dir():
            continue
        for version_dir in sorted(event_dir.iterdir()):
            if (version_dir / "schema.avsc").exists():
                results.append((event_dir.name, version_dir.name))
    return results


if __name__ == "__main__":
    # Smoke test: load every discovered event schema and report success/failure per schema.
    failures = []
    for name, version in list_event_schemas():
        try:
            load_event_schema(name, version)
            print(f"OK   {name}/{version}")
        except Exception as e:  # noqa: BLE001 -- deliberate broad catch for a diagnostic CLI tool
            failures.append((name, version, str(e)))
            print(f"FAIL {name}/{version}: {e}")
    for name, version in list_agent_contract_schemas():
        try:
            load_agent_contract_schema(name, version)
            print(f"OK   agent-contracts/{version}/{name}")
        except Exception as e:  # noqa: BLE001
            failures.append((f"agent-contracts/{name}", version, str(e)))
            print(f"FAIL agent-contracts/{version}/{name}: {e}")
    if failures:
        raise SystemExit(f"{len(failures)} schema(s) failed to load")
