from __future__ import annotations

import pytest

from risk_orchestrator_agent.dto.agent_result_dto import (
    AgentResultDTO,
    AgentResultValidationError,
)
from tests.unit.conftest import make_agent_result


def test_valid_envelope_parses() -> None:
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1", "safety_status": "at_risk"})
    dto = AgentResultDTO.from_raw(raw)
    assert dto.zone_id == "zone-17"
    assert dto.domain_name == "worker"
    assert dto.confidence == 0.9


def test_missing_required_field_raises() -> None:
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})
    del raw["confidence"]
    with pytest.raises(AgentResultValidationError):
        AgentResultDTO.from_raw(raw)


def test_confidence_out_of_range_raises() -> None:
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"}, confidence=1.5)
    with pytest.raises(AgentResultValidationError):
        AgentResultDTO.from_raw(raw)


def test_negative_processing_time_raises() -> None:
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})
    raw["processing_time_ms"] = -5
    with pytest.raises(AgentResultValidationError):
        AgentResultDTO.from_raw(raw)


def test_unknown_result_type_raises_on_domain_name_access() -> None:
    raw = make_agent_result(result_type="drone_analysis", payload={})
    dto = AgentResultDTO.from_raw(raw)
    with pytest.raises(AgentResultValidationError):
        _ = dto.domain_name


def test_populated_error_object_is_a_confidence_reducing_signal_not_discarded() -> None:
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})
    raw["error"] = {"code": "timeout", "message": "upstream sensor read failed"}
    dto = AgentResultDTO.from_raw(raw)
    assert dto.has_error is True
