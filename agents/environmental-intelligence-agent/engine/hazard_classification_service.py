"""
SENTINEL - Gas Intelligence Agent
Hazard classification for industrial gas behaviour.
"""

from typing import Dict, Any, List, Optional
from engine.enums import GasBehaviour, Trend
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class HazardClassificationService:
    """
    Service for classifying industrial gas behaviour.
    
    Instead of simple trend, returns industrial behaviour:
    Stable, Accumulating, Diluting, Leaking, Rapid Build-up,
    Intermittent Release, Continuous Release
    """
    
    def __init__(self) -> None:
        """Initialize hazard classification service."""
        logger.info("HazardClassificationService initialized")
    
    async def classify(
        self,
        gas_type: str,
        trend: Trend,
        rate_of_change: float,
        prediction_growth_rate: float,
        leak_probability: str,
        threshold_distance: Optional[float]
    ) -> GasBehaviour:
        """
        Classify industrial gas behaviour.
        
        Args:
            gas_type: Type of gas
            trend: Current trend direction
            rate_of_change: Rate of change
            prediction_growth_rate: Predicted growth rate
            leak_probability: Leak probability level
            threshold_distance: Distance to threshold (fraction)
            
        Returns:
            GasBehaviour: Classified behaviour
        """
        # Leaking: high leak probability or sustained increase
        if leak_probability in ["HIGH", "CRITICAL"]:
            if trend == Trend.RAPID_INCREASE:
                return GasBehaviour.RAPID_BUILDUP
            return GasBehaviour.LEAKING
        
        # Continuous Release: steady increase
        if trend == Trend.INCREASING and prediction_growth_rate > 0:
            if rate_of_change > 0.5:
                return GasBehaviour.CONTINUOUS_RELEASE
            return GasBehaviour.ACCUMULATING
        
        # Rapid Build-up: rapid increase
        if trend == Trend.RAPID_INCREASE:
            return GasBehaviour.RAPID_BUILDUP
        
        # Intermittent Release: volatile behaviour
        if trend == Trend.STABLE and abs(rate_of_change) > 0.3:
            return GasBehaviour.INTERMITTENT_RELEASE
        
        # Diluting: decreasing trend
        if trend in [Trend.DECREASING, Trend.RAPID_DECREASE]:
            return GasBehaviour.DILUTING
        
        # Stable
        return GasBehaviour.STABLE
    
    async def classify_all(
        self,
        trends: Dict[str, Dict[str, Any]],
        predictions: Dict[str, Any],
        leak_analyses: Dict[str, Any]
    ) -> Dict[str, GasBehaviour]:
        """
        Classify behaviour for all monitored gases.
        
        Args:
            trends: Trend data per gas
            predictions: Prediction data per gas
            leak_analyses: Leak analysis per gas
            
        Returns:
            Dict[str, GasBehaviour]: Behaviour per gas
        """
        behaviours = {}
        
        all_gases = set(trends.keys()) | set(predictions.keys()) | set(leak_analyses.keys())
        
        for gas in all_gases:
            trend = trends.get(gas, {}).get("trend", Trend.STABLE)
            rate = trends.get(gas, {}).get("rate_of_change", 0.0)
            growth = predictions.get(gas, {}).get("growth_rate", 0.0)
            leak_prob = leak_analyses.get(gas, {}).get("probability", "LOW")
            crossing = predictions.get(gas, {}).get("threshold_crossing_minutes")
            
            behaviours[gas] = await self.classify(
                gas, trend, rate, growth, leak_prob, crossing
            )
        
        return behaviours