"""
SENTINEL - Gas Intelligence Agent
Tests for the industrial decision package and supporting services.
"""

import pytest

from engine.decision_package import IndustrialDecisionPackage, Evidence
from engine.evidence_service import EvidenceService
from engine.sensor_reliability_service import SensorReliabilityService
from engine.timeline_service import TimelineService


class TestIndustrialDecisionPackage:
    """Test the standardized decision package."""

    def test_industrial_decision_package_serialization(self) -> None:
        package = IndustrialDecisionPackage(
            zone="Zone-A",
            plant="Plant-A",
            equipment="Reactor-01",
            risk_score=42.0,
            confidence=0.88,
            severity="WARNING",
            decision_reason="Elevated methane trend",
            decision_urgency="HIGH",
            decision_confidence=0.91,
            evidence=[Evidence(source="trend_service", description="Methane rising", confidence=0.9, timestamp=None)],
        )

        payload = package.to_dict()

        assert payload["zone"] == "Zone-A"
        assert payload["risk_score"] == 42.0
        assert payload["decision_reason"] == "Elevated methane trend"
        assert payload["evidence"][0]["source"] == "trend_service"
        assert payload["evidence"][0]["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_evidence_service_generates_structured_evidence(self) -> None:
        service = EvidenceService()
        evidence = await service.generate_evidence(
            threshold_violations=[{"gas_type": "methane", "value": 1200, "threshold_name": "warning"}],
            trends={"methane": {"trend": "INCREASING", "rate_of_change": 1.2, "confidence": 0.86}},
            predictions={"methane": {"threshold_crossing_minutes": 4, "growth_rate": 1.3}},
            correlations=[{"description": "Hydrogen sulfide correlates with methane"}],
            explosion_hazards=[{"description": "Flammable atmosphere detected"}],
            leak_analyses={"methane": {"probability": "HIGH", "confidence": 0.82, "reasons": ["pressure drop"]}},
            gas_behaviours={"methane": "Accumulating"},
            sensor_health={"status": "WARNING", "message": "Sensor drift"},
        )

        assert isinstance(evidence, list)
        assert evidence
        assert all(hasattr(item, "source") for item in evidence)
        assert all(hasattr(item, "timestamp") for item in evidence)

    @pytest.mark.asyncio
    async def test_sensor_reliability_service_assesses_reliability(self) -> None:
        service = SensorReliabilityService()
        reliability = await service.assess_reliability(
            sensor_id="sensor-1",
            sensor_health={"status": "WARNING"},
            validation_stats={"total_validations": 20, "failed_validations": 2},
        )

        assert reliability.sensor_id == "sensor-1"
        assert 0.0 <= reliability.reliability_score <= 1.0
        assert reliability.stability in {"EXCELLENT", "GOOD", "FAIR", "POOR"}
        assert isinstance(reliability.communication_quality, str)

    @pytest.mark.asyncio
    async def test_timeline_service_generates_structured_timeline(self) -> None:
        service = TimelineService()
        timeline = await service.generate_timeline(
            predictions={"methane": {"threshold_crossing_minutes": 5}},
            risk_score=72.0,
            severity="HIGH",
            threshold_violations=[{"gas_type": "methane"}],
        )

        assert isinstance(timeline, list)
        assert len(timeline) >= 2
        assert all(hasattr(item, "time_label") for item in timeline)
        assert all(hasattr(item, "time_seconds") for item in timeline)
