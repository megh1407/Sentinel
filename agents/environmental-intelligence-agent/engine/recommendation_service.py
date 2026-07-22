"""
SENTINEL - Gas Intelligence Agent
Intelligent industrial recommendation service.
"""

from typing import Dict, List, Any, Tuple
from engine.enums import RecommendationPriority, Severity
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class RecommendationService:
    """
    Service for generating prioritized industrial safety recommendations.
    
    Recommendations depend on:
    - Risk score, prediction, gas trend, explosion risk, correlation
    """
    
    def __init__(self) -> None:
        """Initialize recommendation service."""
        logger.info("RecommendationService initialized")
    
    async def generate_recommendations(
        self,
        risk_score: float,
        severity: str,
        trends: Dict[str, Any],
        predictions: Dict[str, Any],
        correlations: List[Dict[str, Any]],
        explosion_assessment: Dict[str, Any],
        leak_analyses: Dict[str, Any],
        gas_behaviours: Dict[str, str],
        threshold_violations: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate prioritized recommendations.
        
        Args:
            risk_score: Current risk score
            severity: Risk severity
            trends: Trend data per gas
            predictions: Prediction data
            correlations: Correlation findings
            explosion_assessment: Explosion risk
            leak_analyses: Leak analysis per gas
            gas_behaviours: Classified behaviours
            threshold_violations: Active violations
            
        Returns:
            List[str]: Prioritized recommendations
        """
        recommendations: List[Tuple[str, int]] = []  # (text, priority_score)
        
        # Check for evacuation conditions
        exp_prob = explosion_assessment.get("probability", "LOW")
        if exp_prob in ["HIGH", "CRITICAL"]:
            recommendations.append(("Evacuate Workers from Zone Immediately", 100))
        
        # Check for gas leak
        high_leaks = [g for g, l in leak_analyses.items() if l.get("probability") in ["HIGH", "CRITICAL"]]
        if high_leaks:
            recommendations.append((f"Inspect Gas Pipeline for {', '.join(high_leaks)} Leaks", 95))
        
        # Check for explosive atmosphere
        if exp_prob in ["MEDIUM", "HIGH", "CRITICAL"]:
            recommendations.append(("Suspend Hot Work Immediately", 90))
            recommendations.append(("Eliminate All Ignition Sources", 85))
        
        # Check for toxic atmosphere
        for corr in correlations:
            if corr.get("name") == "TOXIC_ATMOSPHERE":
                recommendations.append(("Use SCBA Equipment - Toxic Atmosphere", 90))
        
        # Check for confined space hazard
        for corr in correlations:
            if corr.get("name") == "OXYGEN_DEFICIENCY":
                recommendations.append(("Stop Confined Space Entry - Oxygen Deficiency", 85))
        
        # Threshold violations
        if threshold_violations:
            violators = list(set(v.get("gas_type") for v in threshold_violations))
            for gas in violators[:3]:
                recommendations.append((f"Investigate {gas} Source - Threshold Exceeded", 70))
        
        # Rapid increase
        for gas_type, t in trends.items():
            if t.get("trend") == "RAPID_INCREASE":
                recommendations.append((f"Increase Ventilation - {gas_type} Rising Rapidly", 75))
            elif t.get("trend") == "INCREASING":
                recommendations.append((f"Monitor {gas_type} Continuously", 50))
        
        # Fire risk
        for corr in correlations:
            if corr.get("name") == "ELEVATED_FIRE_RISK":
                recommendations.append(("Deploy Fire Suppression System", 80))
        
        # Prediction-based
        for gas_type, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None and crossing <= 5 and crossing > 0:
                recommendations.append((f"Prepare for {gas_type} Threshold Breach in {crossing} min", 65))
        
        # Sensor issues
        # Default recommendations
        if risk_score < 20:
            recommendations.append(("Continue Normal Operations", 10))
        elif risk_score < 40:
            recommendations.append(("Continue Normal Operations with Caution", 20))
        
        # Sort by priority and return text only
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in recommendations[:8]]