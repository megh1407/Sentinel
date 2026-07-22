"""
SENTINEL - Gas Intelligence Agent
Industrial summary generation service.
"""

from typing import Dict, Any, List, Optional
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class SummaryService:
    """
    Service for generating professional industrial summaries.
    
    Produces clear, actionable summaries in industrial safety language.
    """
    
    def __init__(self) -> None:
        """Initialize summary service."""
        logger.info("SummaryService initialized")
    
    async def generate_summary(
        self,
        risk_score: float,
        severity: str,
        trends: Dict[str, Any],
        predictions: Dict[str, Any],
        explosion_assessment: Dict[str, Any],
        leak_analyses: Dict[str, Any],
        gas_behaviours: Dict[str, str],
        threshold_violations: List[Dict[str, Any]],
        correlations: List[Dict[str, Any]]
    ) -> str:
        """
        Generate professional industrial summary.
        
        Args:
            risk_score: Current risk score
            severity: Risk severity
            trends: Trend data per gas
            predictions: Prediction data
            explosion_assessment: Explosion risk
            leak_analyses: Leak analysis per gas
            gas_behaviours: Classified behaviours per gas
            threshold_violations: Active violations
            correlations: Active correlations
            
        Returns:
            str: Professional summary
        """
        parts = []
        
        # Key concern
        main_gas = self._find_main_concern(trends, predictions, gas_behaviours)
        if main_gas:
            gas_name = main_gas.replace("_", " ").title()
            behaviour = gas_behaviours.get(main_gas, "stable")
            current_trend = trends.get(main_gas, {}).get("trend", "STABLE")
            parts.append(
                f"{gas_name} concentration is {current_trend.lower().replace('_', ' ')}. "
                f"Current trend indicates probable {behaviour.lower()}."
            )
        
        # Prediction
        for gas_type, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None and crossing > 0:
                gas_name = gas_type.replace("_", " ").title()
                parts.append(
                    f"Threshold crossing is expected within approximately {crossing} minutes "
                    f"for {gas_name}."
                )
        
        # Explosion
        exp_prob = explosion_assessment.get("probability", "LOW")
        if exp_prob in ["MEDIUM", "HIGH", "CRITICAL"]:
            parts.append(f"Explosion probability is {exp_prob.lower()}.")
        
        # Leak
        high_leaks = [
            g for g, l in leak_analyses.items()
            if l.get("probability") in ["HIGH", "CRITICAL"]
        ]
        if high_leaks:
            gases = ", ".join(g.replace("_", " ").title() for g in high_leaks)
            parts.append(f"Possible gas leak detected for {gases}.")
        
        # Correlations
        for corr in correlations:
            parts.append(corr.get("description", "").lower().capitalize() + ".")
        
        # Recommendations intro
        parts.append(
            "Immediate inspection of methane source and increased ventilation are recommended."
        )
        
        return " ".join(parts)
    
    def _find_main_concern(
        self,
        trends: Dict[str, Any],
        predictions: Dict[str, Any],
        behaviours: Dict[str, str]
    ) -> Optional[str]:
        """Find the gas requiring most attention."""
        priority_behaviours = ["Rapid Build-up", "Continuous Release", "Leaking"]
        
        for gas, bhv in behaviours.items():
            if bhv in priority_behaviours:
                return gas
        
        for gas, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None and crossing <= 10:
                return gas
        
        for gas, t in trends.items():
            if t.get("trend") in ["RAPID_INCREASE"]:
                return gas
        
        return next(iter(trends)) if trends else None