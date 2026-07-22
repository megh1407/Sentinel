"""handlers/publishers.py -- EventPublisher.

Publishes the Orchestrator's final `SystemRiskAssessment` (master prompt
S14: publication failure must be handled explicitly, not silently
swallowed).

PHASE 1 INTEGRATION FIX: this module previously targeted an outbound
topic (`sentinel.risk.assessment.v1`) for which no Pydantic/Avro contract
had ever been registered -- `KafkaEventPublisher.publish()` raised
`NotImplementedError` unconditionally, so nothing was ever actually
published. `contracts/kafka/topics.py` (this same package) had already
correctly registered `RISK_SCORE_TOPIC = "sentinel.risk.score.v1"` as the
Orchestrator's real outbound topic -- the real, schema-registered,
already-consumed-by-response_agent contract -- so this file now targets
that instead of inventing a second one. `handlers/risk_score_adapter.py`
does the `SystemRiskAssessment` -> `RiskScoreV1` translation.
"""

from __future__ import annotations

import logging
from typing import Protocol

from risk_orchestrator_agent.contracts.kafka.topics import RISK_SCORE_TOPIC
from risk_orchestrator_agent.domain.models.system_risk_assessment import SystemRiskAssessment
from risk_orchestrator_agent.handlers.risk_score_adapter import to_risk_score_v1

logger = logging.getLogger(__name__)

OUTBOUND_TOPIC = RISK_SCORE_TOPIC


class PublishError(Exception):
    """Raised when publication fails after retries. Caught by the
    Orchestrator's caller (main.py's event loop) -- never silently
    absorbed, per master prompt S14's explicit-failure-handling rule."""


class EventPublisher(Protocol):
    async def publish(self, assessment: SystemRiskAssessment) -> None: ...


class LoggingEventPublisher:
    """Default adapter: structured-logs the assessment. Sufficient for
    local development, tests, and any deployment where no real Kafka
    broker/producer has been wired up for this process yet."""

    async def publish(self, assessment: SystemRiskAssessment) -> None:
        logger.info(
            "system_risk_assessment_published",
            extra={
                "assessment_id": assessment.assessment_id,
                "zone_id": assessment.zone_id,
                "event_id": assessment.event_id,
                "correlation_id": assessment.correlation_id,
                "severity": assessment.severity.value,
                "decision_category": assessment.decision_category.value,
                "escalation_required": assessment.escalation_required,
                "analysis_completeness": assessment.analysis_completeness,
            },
        )


class RiskScoreEventPublisher:
    """Real publisher: adapts `SystemRiskAssessment` -> `RiskScoreV1` and
    publishes it via `sentinel_eventbus.producer.EventProducer` to
    `sentinel.risk.score.v1`, the real topic `response_agent` already
    consumes. Construct with any `EventProducer` -- a `KafkaTransport`-backed
    one in production, an `InMemoryTransport`-backed one for local/dev/test
    (see sentinel_eventbus.in_memory_transport), matching Phase 6's "use
    the project's existing transport mechanism" instruction.
    """

    def __init__(self, producer) -> None:
        """`producer`: `sentinel_eventbus.producer.EventProducer`."""
        self._producer = producer

    async def publish(self, assessment: SystemRiskAssessment) -> None:
        risk_score = to_risk_score_v1(assessment)
        try:
            self._producer.publish(RISK_SCORE_TOPIC, risk_score, key=risk_score.partition_key)
        except Exception as e:  # noqa: BLE001
            raise PublishError(f"failed to publish RiskScoreV1 for assessment {assessment.assessment_id}: {e}") from e
        logger.info(
            "system_risk_assessment_published",
            extra={
                "assessment_id": assessment.assessment_id,
                "risk_score_event_id": str(risk_score.event_id),
                "topic": RISK_SCORE_TOPIC,
                "zone_id": assessment.zone_id,
                "severity": assessment.severity.value,
                "decision_category": assessment.decision_category.value,
                "escalation_required": assessment.escalation_required,
                "analysis_completeness": assessment.analysis_completeness,
            },
        )


# Backwards-compatible alias: earlier code/docs in this package referred
# to this as KafkaEventPublisher. Keep the name resolvable rather than
# silently breaking an existing import, while RiskScoreEventPublisher is
# the name that reflects what it actually does now.
KafkaEventPublisher = RiskScoreEventPublisher
