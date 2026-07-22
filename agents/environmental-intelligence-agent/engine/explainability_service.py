"""
SENTINEL - Gas Intelligence Agent
Explainability engine for risk score transparency.
"""

from typing import Dict, Any, List, Optional, Tuple
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class ExplainabilityService:
    """
    Service for explaining risk scores and decisions.
    
    Returns:
    - Risk factor breakdown per component
    - Decision reasons (why this risk level)
    - Prediction reasons (why this forecast)
    - Confidence reasons (why this confidence)
    """
    
    def __init__(self) -> None:
        """Initialize explainability service."""
        logger.info("ExplainabilityService initialized")
    
    async def generate_explanation(
        self,
        score_breakdown: Dict[str, float],
        risk_score: float,
        severity: str,
        threshold_violations: List[Dict[str, Any]],
        trends: Dict[str, Any],
        predictions: Dict[str, Any],
        correlations: List[Dict[str, Any]],
        explosion_assessment: Dict[str, Any],
        leak_analysis: Dict[str, Any],
        sensor_health: Dict[str, Any],
        gas_behaviour: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive explanation.
        
        Args:
            score_breakdown: Component risk scores
            risk_score: Overall risk score
            severity: Risk severity
            threshold_violations: List of violations
            trends: Trend data
            predictions: Prediction data
            correlations: Correlation findings
            explosion_assessment: Explosion risk
            leak_analysis: Gas leak analysis
            sensor_health: Sensor diagnostics
            gas_behaviour: Classified gas behaviour
            
        Returns:
            Dict[str, Any]: Explanation with reasons
        """
        risk_factors = score_breakdown.copy()
        
        decision_reasons = self._generate_decision_reasons(
            risk_score, severity, threshold_violations, trends, gas_behaviour
        )
        
        prediction_reasons = self._generate_prediction_reasons(predictions)
        
        confidence_reasons = self._generate_confidence_reasons(
            sensor_health, leak_analysis, len(predictions)
        )
        
        return {
            "risk_factors": risk_factors,
            "decision_reason": "; ".join(decision_reasons),
            "prediction_reason": "; ".join(prediction_reasons),
            "confidence_reason": "; ".join(confidence_reasons)
        }
    
    def _generate_decision_reasons(
        self,
        risk_score: float,
        severity: str,
        violations: List[Dict[str, Any]],
        trends: Dict[str, Any],
        gas_behaviour: str
    ) -> List[str]:
        """Generate reasons for the risk decision."""
        reasons = []
        
        if risk_score >= 60:
            reasons.append(f"High composite risk score of {risk_score:.0f}")
        
        if violations:
            gas_names = [v.get("gas_type", "") for v in violations[:3]]
            reasons.append(f"Threshold violations detected for: {', '.join(gas_names)}")
        
        increasing_gases = [
            g for g, t in trends.items()
            if t.get("trend") in ["INCREASING", "RAPID_INCREASE"]
        ]
        if increasing_gases:
            reasons.append(f"Increasing trend for: {', '.join(increasing_gases[:3])}")
        
        if gas_behaviour in ["Leaking", "Rapid Build-up", "Continuous Release"]:
            reasons.append(f"Gas behaviour classified as {gas_behaviour}")
        
        if not reasons:
            reasons.append("All parameters within normal range")
        
        return reasons
    
    def _generate_prediction_reasons(self, predictions: Dict[str, Any]) -> List[str]:
        """Generate reasons for predictions."""
        reasons = []
        
        for gas_type, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None:
                if crossing == 0:
                    reasons.append(f"{gas_type} has already exceeded threshold")
                elif crossing <= 5:
                    reasons.append(f"{gas_type} threshold expected within {crossing} minutes")
                elif crossing <= 15:
                    reasons.append(f"{gas_type} threshold expected within ~{crossing} minutes")
                elif crossing <= 60:
                    reasons.append(f"{gas_type} threshold expected within {crossing} minutes")
        
        if not reasons:
            reasons.append("No threshold crossing predicted in near term")
        
        return reasons[:3]
    
    def _generate_confidence_reasons(
        self,
        sensor_health: Dict[str, Any],
        leak_analysis: Dict[str, Any],
        prediction_count: int
    ) -> List[str]:
        """Generate reasons for confidence level."""
        reasons = []
        
        health_status = sensor_health.get("status", "HEALTHY")
        if health_status != "HEALTHY":
            reasons.append(f"Confidence reduced: sensor status is {health_status}")
        else:
            reasons.append("All sensors operating normally")
        
        leak_conf = leak_analysis.get("confidence", 0)
        if leak_conf > 0.7:
            reasons.append("Leak analysis confidence is high")
        elif leak_conf < 0.3:
            reasons.append("Limited data for leak analysis")
        
        if prediction_count >= 4:
            reasons.append("Sufficient prediction data available")
        else:
            reasons.append("Limited prediction data")
        
        return reasons