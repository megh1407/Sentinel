import datetime
import uuid
from dataclasses import dataclass, field

from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1

from worker_safety_agent import WorkerSafetyAgent
from zone_ppe_requirements import ZonePPERequirements


class _FakeLogger:
    def __init__(self):
        self.records: list[tuple[str, str, dict]] = []

    def info(self, msg, **kwargs):
        self.records.append(("info", msg, kwargs))

    def warning(self, msg, **kwargs):
        self.records.append(("warning", msg, kwargs))


@dataclass
class _FakeContainer:
    logger: _FakeLogger = field(default_factory=_FakeLogger)
    agent_name: str = "WorkerSafetyAgent"
    state: object = None
    metrics: object = None
    health: object = None


def _make_worker_event(zone_id="Z-104", event_kind=WorkerEventKind.PPE_STATUS, ppe_status=None, worker_id="W-1"):
    return WorkerEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(),
        producer_service="ppe-vision-service",
        producer_version="1.0.0",
        site_id="SITE-01",
        zone_id=zone_id,
        partition_key=zone_id,
        metadata=Metadata(schema_id=200, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=event_kind, ppe_status=ppe_status),
    )


def _build_agent(required_ppe_by_zone=None):
    agent = WorkerSafetyAgent(zone_ppe_requirements=ZonePPERequirements(per_zone=required_ppe_by_zone or {}))
    agent.container = _FakeContainer()
    return agent


def test_ppe_status_event_is_evaluated_and_logged():
    agent = _build_agent(required_ppe_by_zone={"Z-104": ["helmet", "vest"]})
    event = _make_worker_event(zone_id="Z-104", ppe_status={"helmet": True, "vest": False})

    result = agent.process(event)

    # Phase 2 remediation note (SENTINEL forensic audit, P1-2): this used
    # to assert `result is None`, per a documented (now-closed) gap --
    # see worker_safety_agent.py's module docstring, which states
    # process() "now builds and returns a real WorkerAnalysisV1" and
    # names the same two gaps (no generated model, schema provider never
    # preloaded agent-contracts) closed elsewhere in this remediation.
    # The stale side here was this assertion, not the implementation.
    from sentinel_contracts.agent_contracts.worker_analysis_v1 import WorkerAnalysisV1, WorkerSafetyStatus

    assert isinstance(result, WorkerAnalysisV1)
    assert result.payload.ppe_violations == ["vest"]
    assert result.payload.safety_status == WorkerSafetyStatus.at_risk
    assert "W-1" in agent.last_results
    computed = agent.last_results["W-1"]
    assert computed.ppe_violations == ["vest"]

    info_records = [r for r in agent.container.logger.records if r[0] == "info"]
    assert len(info_records) == 1
    assert info_records[0][2]["ppe_violations"] == ["vest"]


def test_non_ppe_status_event_kind_is_ignored():
    agent = _build_agent()
    event = _make_worker_event(event_kind=WorkerEventKind.ZONE_ENTRY, ppe_status=None)

    result = agent.process(event)

    assert result is None
    assert agent.last_results == {}
    assert agent.container.logger.records == []


def test_unexpected_event_type_logs_warning_and_returns_none():
    agent = _build_agent()

    result = agent.process(object())  # not a WorkerEventV1

    assert result is None
    warnings = [r for r in agent.container.logger.records if r[0] == "warning"]
    assert len(warnings) == 1
