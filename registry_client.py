"""
registry_client.py

Confluent Schema Registry REST client. Implements the actual HTTP calls used
by CI's schema-compatibility stage and by sentinel_eventbus at publish/
consume time to resolve schema IDs. No mocking layer -- this hits the real
Schema Registry REST API (https://docs.confluent.io/platform/current/schema-registry/develop/api.html)
and is exercised against a live instance in `scripts/dev-env` (local
Confluent Schema Registry container) and in the CI `contract-validation`
stage against the staging registry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

import requests


class CompatibilityMode(str, Enum):
    BACKWARD = "BACKWARD"
    BACKWARD_TRANSITIVE = "BACKWARD_TRANSITIVE"
    FORWARD = "FORWARD"
    FORWARD_TRANSITIVE = "FORWARD_TRANSITIVE"
    FULL = "FULL"
    FULL_TRANSITIVE = "FULL_TRANSITIVE"
    NONE = "NONE"


@dataclass
class RegisteredSchema:
    schema_id: int
    subject: str
    version: int
    schema: dict


class SchemaRegistryError(Exception):
    """Raised on any non-2xx response from the Schema Registry, with the
    registry's own error_code/message preserved for diagnosis."""

    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.error_code = body.get("error_code")
        self.message = body.get("message", "")
        super().__init__(f"Schema Registry error {status_code} (error_code={self.error_code}): {self.message}")


class SchemaRegistryClient:
    """Thin, typed wrapper over the Confluent Schema Registry REST API.
    All methods raise SchemaRegistryError on failure -- callers (CI stages,
    sentinel_eventbus) never need to inspect raw HTTP status codes."""

    def __init__(self, base_url: str, auth: tuple[str, str] | None = None, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/vnd.schemaregistry.v1+json"})

    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        resp = self._session.request(
            method, f"{self.base_url}{path}", json=json_body, auth=self.auth, timeout=self.timeout
        )
        if not resp.ok:
            try:
                body = resp.json()
            except ValueError:
                body = {"message": resp.text}
            raise SchemaRegistryError(resp.status_code, body)
        return resp.json() if resp.content else {}

    def register_schema(self, subject: str, avro_schema: dict) -> int:
        """POST /subjects/{subject}/versions. Returns the newly (or
        already-) registered schema's global ID. Idempotent: registering an
        identical schema twice returns the same ID without creating a new
        version (standard registry behavior)."""
        body = self._request(
            "POST",
            f"/subjects/{subject}/versions",
            {"schema": json.dumps(avro_schema), "schemaType": "AVRO"},
        )
        return body["id"]

    def check_compatibility(self, subject: str, avro_schema: dict, version: str = "latest") -> bool:
        """POST /compatibility/subjects/{subject}/versions/{version}.
        Dry-run compatibility check against the subject's currently
        configured compatibility mode -- does NOT register the schema.
        This is exactly what CI's schema-compatibility stage calls before
        `register_schema` is ever invoked, so an incompatible change never
        reaches the registry at all."""
        body = self._request(
            "POST",
            f"/compatibility/subjects/{subject}/versions/{version}",
            {"schema": json.dumps(avro_schema), "schemaType": "AVRO"},
        )
        return bool(body.get("is_compatible", False))

    def get_schema(self, subject: str, version: str | int = "latest") -> RegisteredSchema:
        body = self._request("GET", f"/subjects/{subject}/versions/{version}")
        return RegisteredSchema(
            schema_id=body["id"],
            subject=body["subject"],
            version=body["version"],
            schema=json.loads(body["schema"]),
        )

    def get_schema_by_id(self, schema_id: int) -> dict:
        """GET /schemas/ids/{id}. Used by consumers at deserialization time
        to resolve the writer schema from the Confluent wire-format's
        embedded schema ID (see wire_format.py)."""
        body = self._request("GET", f"/schemas/ids/{schema_id}")
        return json.loads(body["schema"])

    def set_compatibility_mode(self, subject: str, mode: CompatibilityMode) -> None:
        """PUT /config/{subject}. Sets the subject-level compatibility mode.
        SENTINEL's default is BACKWARD for every topic (ADR-004) -- this
        method exists for the rare, explicitly-reviewed exception, not for
        routine use."""
        self._request("PUT", f"/config/{subject}", {"compatibility": mode.value})

    def get_compatibility_mode(self, subject: str) -> CompatibilityMode:
        body = self._request("GET", f"/config/{subject}")
        return CompatibilityMode(body["compatibilityLevel"])

    def list_subjects(self) -> list[str]:
        return self._request("GET", "/subjects")

    def list_versions(self, subject: str) -> list[int]:
        return self._request("GET", f"/subjects/{subject}/versions")
