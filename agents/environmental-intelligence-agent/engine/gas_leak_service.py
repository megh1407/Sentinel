"""
SENTINEL - Gas Intelligence Agent
Gas leak analysis service using multi-factor detection.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from engine.enums import LeakProbability, Trend
from engine.history_manager import HistoryManager
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class GasLeakAnalysisService:
    """
    Service for estimating gas leak probability.
    
    Uses: rate of rise, prediction trend, historical patterns.
    Does NOT simply check thresholds.
    """
    
    def __init__(self, history_manager: HistoryManager) -> None:
        """Initialize with history manager."""
        self.history_manager = history_manager
        logger.info("GasLeakAnalysisService initialized")
    
    async def analyze_leak(
        self,
        zone: str,
        gas_type: str,
        current_value: float,
        trend: Trend,
        prediction_growth_rate: float,
        threshold_crossing_minutes: Optional[int]
    ) -> Dict[str, Any]:
        """
        Analyze gas leak probability.
        
        Args:
            zone: Zone identifier
            gas_type: Gas type
            current_value: Current concentration
            trend: Current trend direction
            prediction_growth_rate: Predicted growth rate
            threshold_crossing_minutes: Minutes until threshold crossing
            
        Returns:
            Dict[str, Any]: Leak analysis with probability, confidence, reason
        """
        history = self.history_manager.get_history(zone, limit=15)
        values = [h.get(gas_type, 0) for h in history if h.get(gas_type) is not None]
        values.append(current_value)
        
        leak_score = 0.0
        reasons = []
        
        # Factor 1: Rate of rise (sudden spike detection)
        if len(values) >= 3:
            recent = values[-3:]
            rate_of_rise = (recent[-1] - recent[0]) / max(recent[0], 1)
            if rate_of_rise > 0.5:
                leak_score += 35
                reasons.append(f"Sudden spike: {rate_of_rise:.1%} rise in last 3 readings")
            elif rate_of_rise > 0.2:
                leak_score += 20
                reasons.append(f"Moderate rise: {rate_of_rise:.1%} increase detected")
        
        # Factor 2: Trend direction
        if trend in [Trend.RAPID_INCREASE]:
            leak_score += 25
            reasons.append("Rapidly increasing trend detected")
        elif trend in [Trend.INCREASING]:
            leak_score += 15
            reasons.append("Continuous increase detected")
        
        # Factor 3: Prediction
        if prediction_growth_rate > 0:
            normalized_growth = min(1.0, prediction_growth_rate / max(current_value, 1))
            leak_score += normalized_growth * 20
            if normalized_growth > 0.3:
                reasons.append("Predicted growth rate indicates acceleration")
        
        # Factor 4: Threshold crossing proximity
        if threshold_crossing_minutes is not None:
            if threshold_crossing_minutes <= 2:
                leak_score += 20
                reasons.append("Threshold approaching rapidly")
            elif threshold_crossing_minutes <= 10:
                leak_score += 10
                reasons.append("Threshold approaching")
        
        # Factor 5: Historical volatility
        if len(values) >= 5:
            variance = float(np.var(values))
            if variance > 100:
                leak_score += 10
                reasons.append("High historical volatility suggests instability")
        
        # Normalize to 0-100
        leak_score = min(100.0, max(0.0, leak_score))
        
        # Classify probability
        probability, confidence = self._classify_leak(leak_score, len(values))
        
        return {
            "probability": probability,
            "confidence": confidence,
            "leak_score": round(leak_score, 1),
            "reasons": reasons[:3]  # Top 3 reasons
        }
    
    def _classify_leak(self, score: float, data_points: int) -> Tuple[str, float]:
        """Classify leak probability from score."""
        confidence = min(1.0, data_points / 15.0)
        
        if score >= 70:
            return LeakProbability.CRITICAL, confidence
        elif score >= 50:
            return LeakProbability.HIGH, confidence
        elif score >= 25:
            return LeakProbability.MEDIUM, confidence
        else:
            return LeakProbability.LOW, confidence