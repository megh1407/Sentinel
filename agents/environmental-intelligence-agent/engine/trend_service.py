"""
SENTINEL - Gas Intelligence Agent
Trend service for analyzing temporal patterns in gas concentrations.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from engine.enums import Trend
from engine.history_manager import HistoryManager
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class TrendService:
    """
    Service for analyzing trends in gas concentration data.
    
    Responsible for:
    - Temporal trend detection
    - Rate of change analysis
    - Pattern recognition
    - Trend direction classification
    """
    
    def __init__(self, history_manager: HistoryManager) -> None:
        """
        Initialize trend service.
        
        Args:
            history_manager: History manager instance for accessing historical data
        """
        self.history_manager = history_manager
        self._trend_stats: Dict[str, int] = {
            "total_analyses": 0,
            "trends_detected": 0
        }
        logger.info("TrendService initialized")
    
    async def analyze_trend(
        self,
        zone: str,
        gas_type: str,
        current_value: float,
        window_size: int = 10
    ) -> Tuple[Trend, float, float]:
        """
        Analyze trend for a specific gas type in a zone.
        
        Args:
            zone: Zone identifier
            gas_type: Type of gas
            current_value: Current concentration value
            window_size: Number of historical readings to analyze
            
        Returns:
            Tuple[Trend, float, float]: (trend_direction, rate_of_change, confidence)
        """
        self._trend_stats["total_analyses"] += 1
        
        # Get historical data
        history = self.history_manager.get_history(zone, limit=window_size)
        
        if not history or len(history) < 2:
            # Not enough data for trend analysis
            return Trend.STABLE, 0.0, 0.0
        
        # Extract gas values from history
        values = [reading.get(gas_type, 0) for reading in history]
        values.append(current_value)
        
        # Calculate trend
        trend_direction, rate_of_change, confidence = self._calculate_trend(values)
        
        if trend_direction != Trend.STABLE:
            self._trend_stats["trends_detected"] += 1
        
        return trend_direction, rate_of_change, confidence
    
    def _calculate_trend(self, values: List[float]) -> Tuple[Trend, float, float]:
        """
        Calculate trend from a series of values.
        
        Args:
            values: List of concentration values
            
        Returns:
            Tuple[Trend, float, float]: (trend_direction, rate_of_change, confidence)
        """
        if len(values) < 2:
            return Trend.STABLE, 0.0, 0.0
        
        # Use numpy for calculations
        values_array = np.array(values)
        
        # Calculate moving average
        moving_avg = np.mean(values_array)
        
        # Calculate slope using linear regression
        x = np.arange(len(values))
        slope, intercept = np.polyfit(x, values_array, 1)
        
        # Calculate rate of change (normalized by mean)
        if moving_avg > 0:
            normalized_slope = slope / moving_avg
        else:
            normalized_slope = 0.0
        
        # Calculate confidence based on R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((values_array - y_pred) ** 2)
        ss_tot = np.sum((values_array - moving_avg) ** 2)
        
        if ss_tot > 0:
            r_squared = 1 - (ss_res / ss_tot)
            confidence = max(0.0, min(1.0, r_squared))
        else:
            confidence = 0.0
        
        # Determine trend direction based on slope
        trend_params = {
            "stable_threshold": 0.1,
            "increasing_threshold": 0.3,
            "rapid_increase_threshold": 0.7,
            "decreasing_threshold": -0.3,
            "rapid_decrease_threshold": -0.7
        }
        
        if normalized_slope >= trend_params["rapid_increase_threshold"]:
            return Trend.RAPID_INCREASE, slope, confidence
        elif normalized_slope >= trend_params["increasing_threshold"]:
            return Trend.INCREASING, slope, confidence
        elif normalized_slope <= trend_params["rapid_decrease_threshold"]:
            return Trend.RAPID_DECREASE, slope, confidence
        elif normalized_slope <= trend_params["decreasing_threshold"]:
            return Trend.DECREASING, slope, confidence
        else:
            return Trend.STABLE, slope, confidence
    
    async def detect_rapid_changes(
        self,
        zone: str,
        gas_type: str,
        current_value: float,
        threshold: float
    ) -> Tuple[bool, Optional[Trend], float]:
        """
        Detect rapid changes in gas concentration.
        
        Args:
            zone: Zone identifier
            gas_type: Type of gas
            current_value: Current concentration value
            threshold: Threshold value for rapid change detection
            
        Returns:
            Tuple[bool, Optional[Trend], float]: 
                (has_rapid_change, trend_direction, rate_of_change)
        """
        trend_direction, rate_of_change, confidence = await self.analyze_trend(
            zone, gas_type, current_value
        )
        
        # Check if this is a rapid change
        has_rapid_change = trend_direction in [Trend.RAPID_INCREASE, Trend.RAPID_DECREASE]
        
        # Also check if rate of change is significant relative to threshold
        if threshold > 0 and abs(rate_of_change) > threshold * 0.1:
            has_rapid_change = True
        
        return has_rapid_change, trend_direction, rate_of_change
    
    def calculate_rate_of_change(
        self,
        values: List[float],
        time_deltas: List[float]
    ) -> float:
        """
        Calculate rate of change for a series of values.
        
        Args:
            values: List of values
            time_deltas: List of time differences between measurements (in seconds)
            
        Returns:
            float: Rate of change (units per second)
        """
        if len(values) < 2 or len(time_deltas) < 1:
            return 0.0
        
        # Calculate total change
        total_change = values[-1] - values[0]
        
        # Calculate total time
        total_time = sum(time_deltas)
        
        if total_time > 0:
            return total_change / total_time
        return 0.0
    
    def get_trend_stats(self) -> Dict[str, int]:
        """
        Get trend analysis statistics.
        
        Returns:
            Dict[str, int]: Trend statistics
        """
        return self._trend_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset trend statistics."""
        self._trend_stats = {
            "total_analyses": 0,
            "trends_detected": 0
        }
        logger.debug("Trend statistics reset")