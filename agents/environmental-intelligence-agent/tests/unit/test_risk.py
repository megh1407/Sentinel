"""
SENTINEL - Gas Intelligence Agent
Tests for risk service.
"""

import pytest
from typing import Dict, List

from engine.risk_service import RiskService
from engine.enums import Severity


class TestRiskService:
    """Test suite for RiskService."""
    
    @pytest.fixture
    def risk_service(self) -> RiskService:
        """
        Create RiskService instance for testing.
        
        Returns:
            RiskService: Service instance
        """
        return RiskService()
    
    @pytest.fixture
    def sample_gas_readings(self) -> Dict[str, float]:
        """
        Create sample gas readings for testing.
        
        Returns:
            Dict[str, float]: Sample gas readings
        """
        return {
            "methane": 450.0,
            "carbon_monoxide": 12.0,
            "hydrogen_sulfide": 2.0,
            "oxygen": 20.9,
            "voc": 150.0,
            "ammonia": 5.0
        }
    
    @pytest.fixture
    def sample_environmental_data(self) -> Dict[str, float]:
        """
        Create sample environmental data for testing.
        
        Returns:
            Dict[str, float]: Sample environmental data
        """
        return {
            "temperature": 25.0,
            "humidity": 65.0,
            "pressure": 14.7
        }
    
    @pytest.mark.asyncio
    async def test_calculate_risk_score(
        self,
        risk_service: RiskService,
        sample_gas_readings: Dict[str, float],
        sample_environmental_data: Dict[str, float]
    ) -> None:
        """
        Test risk score calculation.
        
        Args:
            risk_service: RiskService instance
            sample_gas_readings: Sample gas readings
            sample_environmental_data: Sample environmental data
        """
        risk_score, severity, risk_breakdown = (
            await risk_service.calculate_risk_score(
                gas_readings=sample_gas_readings,
                environmental_data=sample_environmental_data,
                events=[]
            )
        )
        
        # Placeholder assertions
        assert isinstance(risk_score, float)
        assert isinstance(severity, Severity)
        assert isinstance(risk_breakdown, dict)
        assert 0.0 <= risk_score <= 100.0
    
    @pytest.mark.asyncio
    async def test_assess_individual_gas_risk(self, risk_service: RiskService) -> None:
        """
        Test individual gas risk assessment.
        
        Args:
            risk_service: RiskService instance
        """
        risk_score, severity = (
            await risk_service.assess_individual_gas_risk(
                gas_type="methane",
                concentration=1200.0
            )
        )
        
        # Placeholder assertions
        assert isinstance(risk_score, float)
        assert isinstance(severity, Severity)
        assert 0.0 <= risk_score <= 100.0
    
    def test_classify_risk_level(self, risk_service: RiskService) -> None:
        """
        Test risk level classification.
        
        Args:
            risk_service: RiskService instance
        """
        # Test different risk scores
        assert risk_service.classify_risk_level(10.0) == Severity.NORMAL
        assert risk_service.classify_risk_level(40.0) == Severity.ADVISORY
        assert risk_service.classify_risk_level(70.0) == Severity.WARNING
        assert risk_service.classify_risk_level(85.0) == Severity.HIGH
        assert risk_service.classify_risk_level(95.0) == Severity.CRITICAL

    def test_calculate_confidence(self, risk_service: RiskService) -> None:
        """Test confidence calculation for risk assessments."""
        confidence = risk_service.calculate_confidence(
            trends={"methane": {"confidence": 0.8}},
            predictions={"methane": {"confidence": 0.9}},
            num_gases=6,
        )

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_calculate_compound_risk(self, risk_service: RiskService) -> None:
        """
        Test compound risk calculation.
        
        Args:
            risk_service: RiskService instance
        """
        multiple_readings = [
            {
                "methane": 450.0,
                "carbon_monoxide": 12.0,
                "zone": "zone-a"
            },
            {
                "methane": 1200.0,
                "carbon_monoxide": 50.0,
                "zone": "zone-b"
            }
        ]
        
        compound_risk, severity, risk_factors = (
            await risk_service.calculate_compound_risk(multiple_readings)
        )
        
        # Placeholder assertions
        assert isinstance(compound_risk, float)
        assert isinstance(severity, Severity)
        assert isinstance(risk_factors, list)
        assert 0.0 <= compound_risk <= 100.0
    
    def test_get_risk_factors(
        self,
        risk_service: RiskService,
        sample_gas_readings: Dict[str, float]
    ) -> None:
        """
        Test risk factor identification.
        
        Args:
            risk_service: RiskService instance
            sample_gas_readings: Sample gas readings
        """
        threshold_violations = [
            {"gas_type": "methane", "severity": "WARNING"},
            {"gas_type": "carbon_monoxide", "severity": "ADVISORY"}
        ]
        
        risk_factors = risk_service.get_risk_factors(
            gas_readings=sample_gas_readings,
            threshold_violations=threshold_violations
        )
        
        # Placeholder assertions
        assert isinstance(risk_factors, list)
    
    def test_get_risk_stats(self, risk_service: RiskService) -> None:
        """
        Test getting risk statistics.
        
        Args:
            risk_service: RiskService instance
        """
        stats = risk_service.get_risk_stats()
        
        assert isinstance(stats, dict)
        assert "total_assessments" in stats
        assert "high_risk_detected" in stats
        assert "critical_risk_detected" in stats
    
    def test_reset_stats(self, risk_service: RiskService) -> None:
        """
        Test resetting statistics.
        
        Args:
            risk_service: RiskService instance
        """
        risk_service.reset_stats()
        stats = risk_service.get_risk_stats()
        
        assert stats["total_assessments"] == 0
        assert stats["high_risk_detected"] == 0
        assert stats["critical_risk_detected"] == 0