# Removed — duplicate generated contract tree

This folder previously contained a second, independently-generated copy of
the Pydantic contract models (`libs/sentinel_contracts/generated/`), alongside
empty `api/` and `events/` placeholder directories.

It has been removed as part of the repository-freeze fixes. Reason:

- It was never imported anywhere in the repository (`agents/`, `libs/`,
  `tests/` all import from the canonical root package, `sentinel_contracts`,
  e.g. `from sentinel_contracts.events.sensor_event_v1 import SensorEventV1`).
- It had already drifted from the canonical copy — e.g. `sensor_event_v1.py`'s
  `sensor_status` field defaulted to the enum member `SensorStatus.ACTIVE` in
  the canonical copy vs. the bare string `"ACTIVE"` here, and this copy
  contained files the canonical copy didn't generate yet (`action_request_v2.py`,
  `confidence_derivation.py`, `environment.py`).

**Canonical location:** the root-level `sentinel_contracts/` package
(`/sentinel_contracts/`), generated from `contracts/**/*.avsc` via
`tools/codegen/avro_to_pydantic.py`. Import from there — do not regenerate
a second copy under `libs/`.

No model, schema, or contract content changed as part of this removal —
only the orphaned duplicate was deleted.
