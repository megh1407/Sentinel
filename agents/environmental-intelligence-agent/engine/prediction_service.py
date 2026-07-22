"""
SENTINEL - Gas Intelligence Agent
Prediction service for forecasting gas concentration trends.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from config import settings
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class PredictionService:
    """
    Service for predicting future gas concentration levels.
    
    Responsible for:
    - Time series forecasting
    - Predictive analytics
    - Confidence scoring
    - Anomaly prediction
    """
    
    def __init__(self) -> None:
        """Initialize prediction service."""
        self._prediction_stats: Dict[str, int] = {
            "total_predictions": 0,
            "successful_predictions": 0,
            "failed_predictions": 0
        }
        logger.info("PredictionService initialized")
    
    async def predict_concentration(
        self,
        gas_type: str,
        historical_values: List[float],
        horizon: int = 5,
        timestamps: Optional[List[object]] = None,
        threshold: Optional[float] = None,
    ) -> Tuple[List[float], List[Dict[str, float]], float]:
        """
        Predict future gas concentrations using lightweight forecasting.
        
        Args:
            gas_type: Type of gas
            historical_values: List of historical concentration values
            horizon: Number of future time steps to predict
            
        Returns:
            Tuple[List[float], float, Optional[int]]: 
                (predicted_values, growth_rate, threshold_crossing_time)
        """
        self._prediction_stats["total_predictions"] += 1
        
        if len(historical_values) < 3:
            # Not enough data for prediction
            return [], [], 0.0
        
        try:
            predicted_values, growth_rate = self._linear_regression_forecast(
                historical_values, horizon
            )
            threshold_crossing = self._estimate_threshold_crossing(
                gas_type, historical_values[-1], growth_rate
            )
            confidence_intervals = []
            for value in predicted_values:
                confidence_intervals.append({"lower_bound": max(0.0, value - 0.05 * max(1.0, value)), "upper_bound": value + 0.05 * max(1.0, value)})
            confidence_score = self.calculate_confidence(historical_values, "default")
            self._prediction_stats["successful_predictions"] += 1
            return predicted_values, confidence_intervals, confidence_score
            
        except Exception as e:
            logger.error(f"Prediction failed for {gas_type}: {str(e)}")
            self._prediction_stats["failed_predictions"] += 1
            return [], 0.0, None
    
    def _linear_regression_forecast(
        self,
        values: List[float],
        horizon: int
    ) -> Tuple[List[float], float]:
        """
        Perform linear regression forecasting.
        
        Args:
            values: Historical values
            horizon: Number of steps to forecast
            
        Returns:
            Tuple[List[float], float]: (predicted_values, growth_rate)
        """
        values_array = np.array(values)
        
        # Use recent values for better prediction
        window_size = min(len(values), settings.PREDICTION_WINDOW_SIZE)
        recent_values = values_array[-window_size:]
        
        # Fit linear regression
        x = np.arange(len(recent_values))
        slope, intercept = np.polyfit(x, recent_values, 1)
        
        # Calculate moving average for baseline
        moving_avg = np.mean(recent_values)
        
        # Blend linear regression with moving average
        # Weight recent trend more heavily
        blend_factor = 0.7
        adjusted_slope = slope * blend_factor + (moving_avg - recent_values[0]) / len(recent_values) * (1 - blend_factor)
        
        # Generate predictions
        predicted_values = []
        last_value = values[-1]
        
        for i in range(horizon):
            next_value = last_value + adjusted_slope * (i + 1)
            # Ensure non-negative predictions
            next_value = max(0.0, next_value)
            predicted_values.append(next_value)
        
        # Calculate growth rate (per time unit)
        growth_rate = adjusted_slope
        
        return predicted_values, growth_rate
    
    def _estimate_threshold_crossing(
        self,
        gas_type: str,
        current_value: float,
        growth_rate: float
    ) -> Optional[int]:
        """
        Estimate time to threshold crossing.
        
        Args:
            gas_type: Type of gas
            current_value: Current concentration
            growth_rate: Growth rate per time unit
            
        Returns:
            Optional[int]: Minutes until threshold crossing, or None if not crossing
        """
        if growth_rate <= 0:
            return None
        
        # Get threshold for gas type
        threshold = self._get_threshold(gas_type)
        if threshold is None:
            return None
        
        # Calculate time to cross threshold
        if current_value >= threshold:
            return 0  # Already exceeded
        
        if growth_rate > 0:
            time_to_cross = (threshold - current_value) / growth_rate
            # Convert to minutes (assuming readings are every minute)
            minutes_to_cross = int(np.ceil(time_to_cross))
            return max(1, minutes_to_cross)
        
        return None
    
    def _get_threshold(self, gas_type: str) -> Optional[float]:
        """
        Get warning threshold for a gas type.
        
        Args:
            gas_type: Type of gas
            
        Returns:
            Optional[float]: Threshold value
        """
        threshold_map = {
            "methane": settings.THRESHOLD_METHANE_PPM,
            "carbon_monoxide": settings.THRESHOLD_CARBON_MONOXIDE_PPM,
            "hydrogen_sulfide": settings.THRESHOLD_HYDROGEN_SULFIDE_PPM,
            "oxygen": settings.THRESHOLD_OXYGEN_PERCENT,
            "voc": settings.THRESHOLD_VOC_PPM,
            "ammonia": settings.THRESHOLD_AMMONIA_PPM,
            "temperature": settings.THRESHOLD_TEMPERATURE_CELSIUS,
            "humidity": settings.THRESHOLD_HUMIDITY_PERCENT,
            "pressure": settings.THRESHOLD_PRESSURE_PSI
        }
        
        return threshold_map.get(gas_type)
    
    async def predict_threshold_breach(
        self,
        gas_type: str,
        current_value: float,
        historical_values: List[float],
        threshold: Optional[float] = None,
    ) -> Tuple[bool, Optional[int], float]:
        """
        Predict if a threshold will be breached in the future.
        
        Args:
            gas_type: Type of gas
            current_value: Current concentration value
            historical_values: List of historical values
            
        Returns:
            Tuple[bool, Optional[int], float]: 
                (will_breach, time_to_breach_steps, confidence)
        """
        predicted_values, _, _ = await self.predict_concentration(gas_type, historical_values)
        threshold_value = threshold or self._get_threshold(gas_type)
        threshold_crossing = None
        if threshold_value is not None and current_value < threshold_value:
            growth_rate = self._estimate_growth_rate(historical_values)
            if growth_rate > 0:
                threshold_crossing = max(1, int(np.ceil((threshold_value - current_value) / growth_rate)))
        will_breach = threshold_crossing is not None and threshold_crossing > 0
        confidence = self._calculate_confidence(historical_values)
        return will_breach, threshold_crossing, confidence
    
    def calculate_confidence(self, historical_values: List[float], prediction_method: Optional[str] = None) -> float:
        """
        Calculate confidence score for predictions.
        
        Args:
            historical_values: List of historical values
            
        Returns:
            float: Confidence score (0.0 to 1.0)
        """
        if len(historical_values) < 3:
            return 0.3
        
        # More data points = higher confidence
        data_confidence = min(1.0, len(historical_values) / 10.0)
        
        # Check for consistency (low variance = higher confidence)
        variance = np.var(historical_values)
        mean_val = np.mean(historical_values)
        
        if mean_val > 0:
            cv = np.sqrt(variance) / mean_val  # Coefficient of variation
            consistency_confidence = max(0.0, 1.0 - cv)
        else:
            consistency_confidence = 0.5
        
        # Blend confidence scores
        confidence = (data_confidence * 0.6) + (consistency_confidence * 0.4)
        
        return min(1.0, max(0.0, confidence))

    def _calculate_confidence(self, historical_values: List[float]) -> float:
        return self.calculate_confidence(historical_values)

    def _estimate_growth_rate(self, historical_values: List[float]) -> float:
        if len(historical_values) < 2:
            return 0.0
        values = np.array(historical_values)
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)
        return float(slope)
    
    def validate_prediction_input(
        self,
        values: List[float],
        min_points: int = 3
    ) -> bool:
        """
        Validate input data for prediction.
        
        Args:
            values: List of values
            min_points: Minimum number of data points required
            
        Returns:
            bool: True if valid for prediction
        """
        if len(values) < min_points:
            return False
        
        # Check for valid numeric values
        return all(isinstance(v, (int, float)) and not np.isnan(v) for v in values)
    
    def get_prediction_stats(self) -> Dict[str, int]:
        """
        Get prediction statistics.
        
        Returns:
            Dict[str, int]: Prediction statistics
        """
        return self._prediction_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset prediction statistics."""
        self._prediction_stats = {
            "total_predictions": 0,
            "successful_predictions": 0,
            "failed_predictions": 0
        }
        logger.debug("Prediction statistics reset")