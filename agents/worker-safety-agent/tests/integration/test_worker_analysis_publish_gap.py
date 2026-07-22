"""
test_worker_analysis_publish_gap.py

Master prompt's "no assumptions" rule applies to platform gaps too: don't
just assert a gap exists because the code reads that way -- prove it by
running the real code and watching it fail. This test does that for the
gap documented in worker_safety_agent.py and main.py.

Uses a throwaway Pydantic class named `WorkerAnalysis` purely as a
publish() call target to exercise LocalSchemaProvider's real resolution
path -- this is NOT a stand-in wire model (it's never used to actually
carry PPE data anywhere, never registered in any EVENT_TYPES/model_registry,
and this test is the only place it's ever instantiated). Its only job is
to have the class name "WorkerAnalysis" so EventProducer.publish()'s
`getattr(event, "event_type", type(event).__name__)` resolves to the same
string LocalSchemaProvider would need to have preloaded.
"""
import pytest
from pydantic import BaseModel

from sentinel_common.errors import FatalError
from sentinel_eventbus import EventProducer, InMemoryTransport, LocalSchemaProvider


class WorkerAnalysis(BaseModel):
    """Diagnostic-only stand-in -- see module docstring. Not a contract."""
    worker_id: str
    ppe_compliance: float
    ppe_violations: list[str]


def test_local_schema_provider_never_preloads_agent_contracts():
    """Gap component 2 (see worker_safety_agent.py): confirms directly,
    without going through publish(), that WorkerAnalysis was never loaded
    -- proving this is a schema-provider limitation, not a coincidental
    naming mismatch."""
    provider = LocalSchemaProvider()
    with pytest.raises(KeyError, match="no local schema registered for WorkerAnalysis"):
        provider.get_schema_and_id("WorkerAnalysis", 1)


def test_publishing_worker_analysis_raises_fatal_error():
    """Gap component 2, end-to-end through the real publish() path."""
    schema_provider = LocalSchemaProvider()
    producer = EventProducer(InMemoryTransport(client_id="p"), schema_provider)

    event = WorkerAnalysis(worker_id="W-1", ppe_compliance=0.5, ppe_violations=["gloves"])

    with pytest.raises(FatalError, match="could not resolve schema for WorkerAnalysis"):
        producer.publish("sentinel.worker.analysis.v1", event)


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
