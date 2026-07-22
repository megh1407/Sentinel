"""
SENTINEL - Gas Intelligence Agent
Tests for prediction service.
"""

import pytest
from datetime import datetime, timezone
from typing import List

from engine.prediction_service import PredictionService
from engine.enums import Severity


class TestPredictionService:
    """Test suite for PredictionService."""
    
    @pytest.fixture
    def prediction_service(self) -> PredictionService:
        """
        Create PredictionService instance for testing.
        
        Returns:
            PredictionService: Service instance
        """
        return PredictionService()
    
    @pytest.fixture
    def sample_historical_values(self) -> List[float]:
        """
        Create sample historical values for testing.
        
        Returns:
            List[float]: Sample historical values
        """
        return [100.0, 105.0, 110.0, 115.0, 120.0]
    
    @pytest.fixture
    def sample_timestamps(self) -> List[datetime]:
        """
        Create sample timestamps for testing.
        
        Returns:
            List[datetime]: Sample timestamps
        """
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return [base_time.replace(minute=i) for i in range(5)]
    
    @pytest.mark.asyncio
    async def test_predict_concentration(
        self,
        prediction_service: PredictionService,
        sample_historical_values: List[float],
        sample_timestamps: List[datetime]
    ) -> None:
        """
        Test concentration prediction.
        
        Args:
            prediction_service: PredictionService instance
            sample_historical_values: Sample historical values
            sample_timestamps: Sample timestamps
        """
        predicted_values, confidence_intervals, confidence_score = (
            await prediction_service.predict_concentration(
                gas_type="methane",
                historical_values=sample_historical_values,
                timestamps=sample_timestamps,
                horizon=5
            )
        )
        
        # Placeholder assertions
        # Will be implemented when business logic is added
        assert isinstance(predicted_values, list)
        assert isinstance(confidence_intervals, list)
        assert isinstance(confidence_score, float)
    
    @pytest.mark.asyncio
    async def test_predict_threshold_breach(self, prediction_service: PredictionService) -> None:
        """
        Test threshold breach prediction.
        
        Args:
            prediction_service: PredictionService instance
        """
        will_breach, time_to_breach, confidence = (
            await prediction_service.predict_threshold_breach(
                gas_type="methane",
                current_value=500.0,
                historical_values=[400.0, 450.0, 480.0, 490.0, 500.0],
                threshold=1000.0
            )
        )
        
        # Placeholder assertions
        assert isinstance(will_breach, bool)
        assert isinstance(confidence, float)
    
    def test_calculate_confidence(self, prediction_service: PredictionService) -> None:
        """
        Test confidence calculation.
        
        Args:
            prediction_service: PredictionService instance
        """
        confidence = prediction_service.calculate_confidence(
            historical_values=[100.0, 105.0, 110.0],
            prediction_method="default"
        )
        
        # Placeholder assertions
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
    
    def test_validate_prediction_input(self, prediction_service: PredictionService) -> None:
        """
        Test prediction input validation.
        
        Args:
            prediction_service: PredictionService instance
        """
        # Valid input
        assert prediction_service.validate_prediction_input([1.0, 2.0, 3.0], min_points=3) is True
        
        # Invalid input (too few points)
        assert prediction_service.validate_prediction_input([1.0, 2.0], min_points=3) is False
    
    def test_get_prediction_stats(self, prediction_service: PredictionService) -> None:
        """
        Test getting prediction statistics.
        
        Args:
            prediction_service: PredictionService instance
        """
        stats = prediction_service.get_prediction_stats()
        
        assert isinstance(stats, dict)
        assert "total_predictions" in stats
        assert "successful_predictions" in stats
        assert "failed_predictions" in stats
    
    def test_reset_stats(self, prediction_service: PredictionService) -> None:
        """
        Test resetting statistics.
        
        Args:
            prediction_service: PredictionService instance
        """
        prediction_service.reset_stats()
        stats = prediction_service.get_prediction_stats()
        
        assert stats["total_predictions"] == 0
        assert stats["successful_predictions"] == 0
        assert stats["failed_predictions"] == 0