"""
test_worker_analysis_publish_gap.py

This module originally documented (and experimentally proved) a real gap:
`LocalSchemaProvider` only preloaded `contracts/events/*` schemas, not
`contracts/agent-contracts/*` schemas, so publishing a `WorkerAnalysis`
(or any other intelligence agent's analysis output) failed with
"no local schema registered". That gap has since been closed --
`sentinel_eventbus/schema_provider.py`'s `_preload()` now loads agent-
contract schemas too (see that file's own comment for the history) -- and
`platform-services/api-gateway`'s `orchestrator_runtime.py`/`state_cache.py`
already register `WorkerAnalysisV1` under the `"WorkerAnalysis"` key in
their own real `model_registry` dicts, confirming this is the canonical,
already-working registration path, not a new one invented here.

Phase 2 remediation note (SENTINEL forensic audit, P0-3): these two tests
were not updated when the schema-provider fix landed, so they kept
asserting the pre-fix failure modes (`KeyError` / `FatalError`) that no
longer occur -- i.e. the *tests* were stale, not the implementation.
Verified via `git log`-equivalent reasoning is unavailable here, but the
evidence is direct: running the fix's own code path today no longer
raises either exception. Rewritten below to assert the current, correct,
intended behavior instead of the historical gap.
"""
from pydantic import BaseModel

from sentinel_eventbus import EventProducer, InMemoryTransport, LocalSchemaProvider


class WorkerAnalysis(BaseModel):
    """Diagnostic-only stand-in -- see module docstring. Not a contract."""
    worker_id: str
    ppe_compliance: float
    ppe_violations: list[str]


def test_local_schema_provider_preloads_agent_contracts():
    """Confirms directly, without going through publish(), that
    WorkerAnalysis (an agent-contracts/ schema, not an events/ schema) is
    now preloaded by LocalSchemaProvider -- proving the schema-provider
    fix covers agent-contract schemas generally, not just this one type
    as a special case."""
    provider = LocalSchemaProvider()
    schema, schema_id = provider.get_schema_and_id("WorkerAnalysis", 1)
    assert schema is not None
    assert isinstance(schema_id, int)


def test_publishing_worker_analysis_succeeds():
    """End-to-end through the real publish() path, using a fully-formed
    real WorkerAnalysisV1 (not a minimal stand-in -- the full envelope,
    including required fields like event_id, is part of what Avro
    encoding actually needs, so a partial model isn't a fair proof
    here): an agent-contracts event type now resolves a schema and
    publishes without error, the same way an events/ type like
    WorkerEvent always could."""
    import datetime
    import uuid

    from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
    from sentinel_contracts.common.explanation_object import ExplanationObject
    from sentinel_contracts.common.metadata import Environment, Metadata
    from sentinel_contracts.agent_contracts.worker_analysis_v1 import (
        WorkerAnalysisPayload, WorkerAnalysisV1, WorkerSafetyStatus,
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    event = WorkerAnalysisV1(
        event_id=uuid.uuid4(),
        event_timestamp=now,
        correlation_id=uuid.uuid4(),
        producer_service="worker_safety_agent",
        producer_version="0.2.0",
        site_id="SITE-01",
        zone_id="Z-104",
        partition_key="Z-104",
        metadata=Metadata(schema_id=1, schema_version=1, environment=Environment.DEV),
        agent_id="worker_safety_agent",
        agent_version="0.2.0",
        input_events=[uuid.uuid4()],
        confidence=1.0,
        processing_time_ms=0,
        explanation=ExplanationObject(
            summary="Worker W-1 is missing required PPE: gloves in zone Z-104.",
            confidence=ConfidenceScore(value=1.0, derivation=ConfidenceDerivation.RULE_BASED),
            evidence=[],
            reasoning_steps=[],
            generated_at=now,
        ),
        payload=WorkerAnalysisPayload(
            worker_id="W-1",
            risk_score=50.0,
            confidence=1.0,
            safety_status=WorkerSafetyStatus.at_risk,
            ppe_compliance=0.5,
            ppe_violations=["gloves"],
            evidence=[],
            recommendations=[],
            analyzed_at=now,
        ),
    )

    schema_provider = LocalSchemaProvider()
    producer = EventProducer(InMemoryTransport(client_id="p"), schema_provider)

    result = producer.publish("sentinel.worker.analysis.v1", event)
    assert result is not None


def test_worker_event_by_contrast_publishes_fine():
    """Control case: WorkerEvent (contracts/events/WorkerEvent/, NOT
    contracts/agent-contracts/) IS preloaded and publishes without error --
    isolating the gap to schemas living under contracts/agent-contracts/
    specifically, not to this producer/transport/schema-provider stack in
    general."""
    import datetime
    import uuid

    from sentinel_contracts.common.metadata import Environment, Metadata
    from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1

    schema_provider = LocalSchemaProvider()
    producer = EventProducer(InMemoryTransport(client_id="p"), schema_provider)

    event = WorkerEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(), producer_service="ppe-vision-service", producer_version="0.1.0-demo",
        site_id="SITE-01", zone_id="Z-104", partition_key="Z-104",
        metadata=Metadata(schema_id=200, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(worker_id="W-1", event_kind=WorkerEventKind.PPE_STATUS, ppe_status={"helmet": True}),
    )

    result = producer.publish("sentinel.worker.events.v1", event)
    assert result is not None
