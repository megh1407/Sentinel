"""Kafka topic name constants (Phase 1 §4, §5).

These are references to the platform's already-registered topic names
(`contracts/topics/kafka_topics.yaml`), not a redefinition of them — this
module exists so `handlers/consumers.py`/`publishers.py` (a later phase)
and this domain layer's tests never hand-type a topic string more than
once.
"""

from __future__ import annotations

# --- Inbound: six Intelligence Agent analysis topics ------------------------
WORKER_ANALYSIS_TOPIC = "sentinel.worker.analysis.v1"
ZONE_ANALYSIS_TOPIC = "sentinel.zone.analysis.v1"
PERMIT_ANALYSIS_TOPIC = "sentinel.permit.analysis.v1"
MAINTENANCE_ANALYSIS_TOPIC = "sentinel.maintenance.analysis.v1"
ENVIRONMENT_ANALYSIS_TOPIC = "sentinel.environment.analysis.v1"
INCIDENT_ANALYSIS_TOPIC = "sentinel.incident.analysis.v1"

INBOUND_TOPICS: tuple[str, ...] = (
    WORKER_ANALYSIS_TOPIC,
    ZONE_ANALYSIS_TOPIC,
    PERMIT_ANALYSIS_TOPIC,
    MAINTENANCE_ANALYSIS_TOPIC,
    ENVIRONMENT_ANALYSIS_TOPIC,
    INCIDENT_ANALYSIS_TOPIC,
)

# --- Outbound: Risk Orchestrator's own topics -------------------------------
RISK_SCORE_TOPIC = "sentinel.risk.score.v1"
SITE_STATE_TOPIC = "sentinel.site.state.v1"
PREDICTION_TOPIC = "sentinel.prediction.v1"

OUTBOUND_TOPICS: tuple[str, ...] = (RISK_SCORE_TOPIC, SITE_STATE_TOPIC, PREDICTION_TOPIC)


def dlq_topic_for(topic: str) -> str:
    """The platform-wide DLQ naming convention (Phase 2.1 §3.1): every
    topic `T` routes permanently-failed messages to `sentinel.dlq.T`.
    """
    return f"sentinel.dlq.{topic}"
