"""
ppe_compliance_service.py

Pure, dependency-free business logic:

    detected PPE (WorkerEventPayload.ppe_status: dict[str, bool])
            +
    required PPE (list[str], from ZonePPERequirements -- see that module's
    docstring for why this isn't sourced from an event today)
            v
    compliance result

This is internal-only, per the master prompt's instruction ("Create a small
internal service only if necessary... must not become a new wire
contract"). It is deliberately NOT a Pydantic model bound to any Avro
schema -- it's a plain dataclass any caller (the agent, a unit test, a
demo script) can construct and inspect without touching Kafka, wire
format, or schema resolution at all.

Field names below (`ppe_compliance`, `ppe_violations`) are chosen to match
`contracts/agent-contracts/v1/worker_analysis.schema.json` /
`WorkerAnalysis.avsc` exactly, since the intent is for this dataclass's
`.to_worker_analysis_payload_fragment()` output to be a legal instance of
that frozen schema (validated in
tests/contract/test_worker_analysis_shape.py via jsonschema against the
real committed schema file -- there is no generated Pydantic model to
validate against instead; see README.md's "Known gaps", G2).

IMPORTANT, found only by reading the actual frozen schema rather than
assuming (master prompt step 3's instruction -- and this is exactly why
that instruction exists): `ppe_compliance` is declared as a nullable
`double` in BOTH worker_analysis.schema.json ("type": "number", minimum 0,
maximum 1) and WorkerAnalysis.avsc ("type": ["null", "double"]) -- it is a
compliance *score* in [0, 1], NOT a boolean. A JSON Schema "number"
validator rejects true/false, and Avro's ["null","double"] union has no
"boolean" branch either -- so this file emits a float, not a bool.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PPEComplianceResult:
    worker_id: str
    zone_id: str
    required_ppe: list[str]
    detected_ppe: dict[str, bool]
    ppe_compliance_score: float
    """Fraction of required_ppe items detected as worn/present, in [0, 1].
    1.0 when required_ppe is empty (vacuously fully compliant -- nothing
    was required). This is what worker_analysis.schema.json's
    `ppe_compliance` field actually holds -- NOT a boolean."""
    ppe_violations: list[str] = field(default_factory=list)
    unknown_ppe_keys: list[str] = field(default_factory=list)
    """PPE keys present in detected_ppe that aren't in required_ppe for this
    zone -- not a violation (extra protection is never non-compliant), but
    worth surfacing per the master prompt's step 8 ("determine ... unknown
    PPE"). Kept out of ppe_violations, which is reserved for MISSING
    required items, matching worker_analysis.schema.json's field intent."""

    @property
    def is_fully_compliant(self) -> bool:
        return len(self.ppe_violations) == 0

    def to_worker_analysis_payload_fragment(self) -> dict:
        """The subset of WorkerAnalysis.payload this service is authoritative
        for. Does NOT include risk_score/safety_status/confidence/zone_clearance/
        proximity_alerts/evidence/recommendations -- those are either not yet
        computed by this agent or belong to other rules; returning them here
        would mean fabricating fields this service has no basis to fill,
        which the master prompt explicitly prohibits (step 8: "Populate only
        fields that already exist ... Preserve the existing WorkerAnalysis
        contract exactly")."""
        return {
            "ppe_compliance": self.ppe_compliance_score,
            "ppe_violations": list(self.ppe_violations),
        }


def evaluate_ppe_compliance(
    *, worker_id: str, zone_id: str, detected_ppe: dict[str, bool] | None, required_ppe: list[str]
) -> PPEComplianceResult:
    """`detected_ppe` may be None (WorkerEventPayload.ppe_status is nullable,
    populated only when event_kind == PPE_STATUS -- see worker_event_v1.py).
    A None/empty detection with a non-empty requirement is treated as full
    non-compliance (every required item is missing), not as "unknown" --
    absence of evidence for a required safety item is not evidence of its
    presence."""
    detected = detected_ppe or {}

    violations = [item for item in required_ppe if not detected.get(item, False)]
    unknown = [key for key in detected.keys() if key not in required_ppe]

    if required_ppe:
        satisfied = len(required_ppe) - len(violations)
        score = satisfied / len(required_ppe)
    else:
        score = 1.0  # nothing required -> vacuously fully compliant

    return PPEComplianceResult(
        worker_id=worker_id,
        zone_id=zone_id,
        required_ppe=list(required_ppe),
        detected_ppe=dict(detected),
        ppe_compliance_score=score,
        ppe_violations=violations,
        unknown_ppe_keys=unknown,
    )
