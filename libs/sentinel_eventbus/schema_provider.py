"""
schema_provider.py

EventProducer/EventConsumer need to resolve (avro_schema, schema_id) for a
given (event_type, version). In production this comes from a live
SchemaRegistryClient (registry_client.py, already built and tested against
the real Confluent REST API contract, but not reachable from this
environment). LocalSchemaProvider is the equivalent for local dev/tests:
it loads schemas directly from contracts/events/*/*/schema.avsc via
schema_loader.py, and assigns a stable, deterministic integer schema_id
per (event_type, version) so wire_format.py's magic-byte framing works
identically to production -- just without a network call.

Swapping LocalSchemaProvider for a RegistrySchemaProvider (thin adapter
over registry_client.SchemaRegistryClient, included below) is the only
change needed to point at a live registry.
"""
from __future__ import annotations

from schema_loader import list_event_schemas, load_event_schema


class LocalSchemaProvider:
    def __init__(self):
        self._schema_cache: dict[tuple[str, int], dict] = {}
        self._id_cache: dict[tuple[str, int], int] = {}
        self._next_id = 100
        self._preload()

    def _preload(self) -> None:
        for name, version in list_event_schemas():
            version_int = int(version.lstrip("v"))
            schema = load_event_schema(name, version)
            key = (name, version_int)
            self._schema_cache[key] = schema
            self._id_cache[key] = self._next_id
            self._next_id += 1

    def get_schema_and_id(self, event_type: str, version: int) -> tuple[dict, int]:
        key = (event_type, int(version))
        if key not in self._schema_cache:
            raise KeyError(f"no local schema registered for {event_type} v{version}")
        return self._schema_cache[key], self._id_cache[key]

    def get_schema_by_id(self, schema_id: int) -> dict:
        for key, sid in self._id_cache.items():
            if sid == schema_id:
                return self._schema_cache[key]
        raise KeyError(f"no schema found for id {schema_id}")


class RegistrySchemaProvider:
    """Production adapter over registry_client.SchemaRegistryClient. Not
    exercised in this environment (no reachable registry), included for
    completeness -- this is the class you point EventProducer/EventConsumer
    at once scripts/dev-env's Schema Registry container (or a real one) is
    reachable."""

    def __init__(self, registry_client):
        self._client = registry_client
        self._id_cache: dict[tuple[str, int], int] = {}
        self._schema_cache: dict[int, dict] = {}

    def get_schema_and_id(self, event_type: str, version: int) -> tuple[dict, int]:
        key = (event_type, int(version))
        if key not in self._id_cache:
            registered = self._client.get_schema(f"{event_type}-value", version)
            self._id_cache[key] = registered.schema_id
            self._schema_cache[registered.schema_id] = registered.schema
        schema_id = self._id_cache[key]
        return self._schema_cache[schema_id], schema_id

    def get_schema_by_id(self, schema_id: int) -> dict:
        if schema_id not in self._schema_cache:
            self._schema_cache[schema_id] = self._client.get_schema_by_id(schema_id)
        return self._schema_cache[schema_id]
