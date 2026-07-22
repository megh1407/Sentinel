"""
permit_lifecycle_validator.py

Phase 2A of the integration master prompt: permit exists, is active
according to the *canonical* status enum (PermitStatus, from
sentinel_contracts.events.permit_event_v1 -- NOT the friend-ZIP's
lifecycle_status vocabulary, which does not exist on the real wire
contract), and is within its validity window.

Deliberately does not check `gas_test_required` or `isolation_points` --
those fields do not exist on PermitEventV1's payload at all (verified
against contracts/events/PermitEvent/v1/schema.avsc and the generated
model). See permit_condition_evaluator.py for why that's not silently
dropped -- it's reported as BLOCKED_BY_INPUT_CONTRACT instead.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sentinel_contracts.events.permit_event_v1 import PermitEventPayload, PermitStatus


class PermitLifecycleValidator:
    def evaluate(self, payload: PermitEventPayload, now: datetime | None = None) -> tuple[bool, list[str]]:
        """Returns (is_valid, findings). is_valid=False means the permit
        should not be treated as authorizing active work right now."""
        now = now or datetime.now(timezone.utc)
        findings: list[str] = []
        is_valid = True

        if payload.status != PermitStatus.ACTIVE:
            is_valid = False
            findings.append(f"PERMIT_NOT_ACTIVE: status={payload.status.value}")

        if now < payload.valid_from:
            is_valid = False
            findings.append(f"PERMIT_NOT_YET_VALID: valid_from={payload.valid_from.isoformat()}")

        if now > payload.valid_until:
            is_valid = False
            findings.append(f"PERMIT_EXPIRED: valid_until={payload.valid_until.isoformat()}")

        return is_valid, findings
