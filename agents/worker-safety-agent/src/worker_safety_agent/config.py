"""
config.py

Phase 2 remediation note (SENTINEL forensic audit, P1-2): this file was
previously empty even though `tests/unit/test_zone_ppe_requirements.py`
(already present in the repository, not added by this remediation)
imports `build_zone_ppe_requirements` from it. Investigated whether the
test or the missing function was the stale side: `zone_ppe_requirements.py`'s
own docstring establishes the intended pattern precisely -- "a small,
internal, dependency-free lookup that an eventual config-service client
can replace without touching any caller" -- mirroring
`zone_intelligence_agent/config.py`'s layered resolver for the identical
"no sentinel_config package exists yet" gap. No real caller in this repo
currently needs anything beyond the literal `ZonePPERequirements(per_zone=...)`
construction already used in `worker_safety_agent.py` and
`demo/run_pipeline_demo.py`, so this function is additive (an optional,
env-var-driven way to build the same object) and does not change any
existing call site's behavior.

`WORKER_SAFETY_REQUIRED_PPE`, if set, is a JSON object mapping zone_id ->
list of required PPE item names (the same shape as `ZonePPERequirements
.per_zone`). Malformed JSON is a configuration error, not something to
guess around -- fails closed via `ConfigurationError`, consistent with
`sentinel_common.errors.ConfigurationError`'s own docstring ("Config
failed validation at load time").
"""
from __future__ import annotations

import json
import os

from sentinel_common.errors import ConfigurationError

from zone_ppe_requirements import ZonePPERequirements

_ENV_VAR = "WORKER_SAFETY_REQUIRED_PPE"


def build_zone_ppe_requirements() -> ZonePPERequirements:
    """Builds `ZonePPERequirements` from `WORKER_SAFETY_REQUIRED_PPE` if
    set, otherwise returns the all-defaults `ZonePPERequirements()`."""
    raw = os.environ.get(_ENV_VAR)
    if raw is None:
        return ZonePPERequirements()

    try:
        per_zone = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"{_ENV_VAR} is not valid JSON: {exc}",
            details={"env_var": _ENV_VAR},
        ) from exc

    if not isinstance(per_zone, dict):
        raise ConfigurationError(
            f"{_ENV_VAR} must be a JSON object mapping zone_id -> [ppe items]",
            details={"env_var": _ENV_VAR},
        )

    return ZonePPERequirements(per_zone=per_zone)
