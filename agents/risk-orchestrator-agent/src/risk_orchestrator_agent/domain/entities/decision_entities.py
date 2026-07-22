"""`Decision` aggregate root, its `DecisionRecord` entities, and the
`EventEnvelope` entity used to wrap inbound/outbound messages
(Phase 2.5 §3.3, §4.3; Phase 2.4 §8; Phase 1 `BaseEvent`/`AgentResult`).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from risk_orchestrator_agent.domain.entities.base import Entity
from risk_orchestrator_agent.domain.enums.status import DecisionState
from risk_orchestrator_agent.shared.utilities.time_utils import utc_now

#: The only transitions `Decision.transition_to` will accept, mirroring
#: Phase 2.4 §8.1 / Phase 2.5 §10.3's state machine exactly.
_ALLOWED_TRANSITIONS: dict[DecisionState, tuple[DecisionState, ...]] = {
    DecisionState.PENDING: (DecisionState.UNDER_EVALUATION,),
    DecisionState.UNDER_EVALUATION: (
        DecisionState.DECISION_CREATED,
    ),
    DecisionState.DECISION_CREATED: (
        DecisionState.EMERGENCY_TIER,
        DecisionState.RECOMMENDATION_FLAGGED,
        DecisionState.RESOLVED,
        DecisionState.CANCELLED,
    ),
    DecisionState.EMERGENCY_TIER: (DecisionState.ACKNOWLEDGED,),
    DecisionState.RECOMMENDATION_FLAGGED: (DecisionState.ACKNOWLEDGED,),
    DecisionState.ACKNOWLEDGED: (DecisionState.RESOLVED,),
    DecisionState.RESOLVED: (DecisionState.CLOSED,),
    DecisionState.CLOSED: (),
    DecisionState.CANCELLED: (),
}


@dataclasses.dataclass(eq=False)
class DecisionRecord(Entity):
    """One immutable state transition within a `Decision`'s lifecycle
    (Phase 2.5 §4.3)."""

    decision_id: str = ""
    previous_state: DecisionState | None = None
    new_state: DecisionState = DecisionState.PENDING
    triggering_assessment_id: str | None = None
    transitioned_at: datetime = dataclasses.field(default_factory=utc_now)


@dataclasses.dataclass(eq=False)
class Decision(Entity):
    """The multi-cycle, per-zone decision lifecycle aggregate root
    (Phase 2.5 §3.3) — tracks state *across* multiple `RiskAssessment`
    publications, distinct from any single cycle's `DecisionOutcome`.
    """

    zone_id: str = ""
    current_state: DecisionState = DecisionState.PENDING
    records: tuple[DecisionRecord, ...] = ()
    referenced_assessment_ids: tuple[str, ...] = ()

    def transition_to(
        self, new_state: DecisionState, *, triggering_assessment_id: str | None = None
    ) -> DecisionRecord:
        """Advance this `Decision`'s state, enforcing Phase 2.4 §8.1's
        state machine (Phase 2.5 §12's "Invalid State Transition"
        validation rule) and appending the resulting `DecisionRecord`.
        """
        from risk_orchestrator_agent.domain.exceptions.base import DomainException

        allowed = _ALLOWED_TRANSITIONS.get(self.current_state, ())
        if new_state not in allowed:
            raise DomainException(
                f"Illegal Decision transition: {self.current_state.value} -> "
                f"{new_state.value} is not permitted (Phase 2.4 §8.1)."
            )
        record = DecisionRecord(
            decision_id=self.entity_id,
            previous_state=self.current_state,
            new_state=new_state,
            triggering_assessment_id=triggering_assessment_id,
        )
        self.records = (*self.records, record)
        self.current_state = new_state
        if triggering_assessment_id and triggering_assessment_id not in self.referenced_assessment_ids:
            self.referenced_assessment_ids = (*self.referenced_assessment_ids, triggering_assessment_id)
        self.touch()
        return record

    def is_terminal(self) -> bool:
        return self.current_state in (DecisionState.CLOSED, DecisionState.CANCELLED)


@dataclasses.dataclass(eq=False)
class EventEnvelope(Entity):
    """The universal wrapper every inbound/outbound message travels in
    (Phase 1's `BaseEvent` + `AgentResult` envelope, Phase 1 §4)."""

    event_type: str = ""
    event_version: int = 1
    source: str = ""
    site_id: str = ""
    zone_id: str = ""
    causation_id: str | None = None
    schema_version: str = "v1"
    agent_id: str = ""
    agent_version: str = ""
    input_events: tuple[str, ...] = ()
    result_type: str = ""
    confidence: float = 0.0
    processing_time_ms: int = 0
    error: str | None = None
    payload: dict = dataclasses.field(default_factory=dict)
    timestamp: datetime = dataclasses.field(default_factory=utc_now)

    def has_error(self) -> bool:
        return self.error is not None
