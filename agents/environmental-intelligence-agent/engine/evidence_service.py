"""
SENTINEL - Gas Intelligence Agent
Evidence engine for providing structured evidence for every decision.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
from engine.decision_package import Evidence
from engine.enums import Trend
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class EvidenceService:
    """
    Generates structured evidence for every analytical decision.
    
    Each evidence item contains:
    - source (which service generated it)
    - description (what was detected)
    - confidence (how sure)
    - timestamp (when)
    """
    
    def __init__(self) -> None:
        """Initialize evidence service."""
        logger.info("EvidenceService initialized")
    
    async def generate_evidence(
        self,
        threshold_violations: List[Dict[str, Any]],
        trends: Dict[str, Any],
        predictions: Dict[str, Any],
        correlations: List[Dict[str, Any]],
        explosion_hazards: List[Dict[str, Any]],
        leak_analyses: Dict[str, Any],
        gas_behaviours: Dict[str, str],
        sensor_health: Dict[str, Any]
    ) -> List[Evidence]:
        """
        Generate structured evidence from all analysis results.
        
        Returns:
            List[Evidence]: Evidence items sorted by confidence descending
        """
        evidence_list: List[Evidence] = []
        now = datetime.now(timezone.utc)
        
        # Evidence from threshold analysis
        for v in threshold_violations:
            evidence_list.append(Evidence(
                source="threshold_service",
                description=f"{v.get('gas_type', 'unknown')} exceeded {v.get('threshold_name', 'NORMAL')} threshold at {v.get('value', 0)}",
                confidence=0.95,
                timestamp=now
            ))
        
        # Evidence from trend analysis
        for gas_type, t in trends.items():
            trend = t.get("trend")
            if isinstance(trend, Trend):
                trend = trend.value
            if trend in ["INCREASING", "RAPID_INCREASE"]:
                evidence_list.append(Evidence(
                    source="trend_service",
                    description=f"{gas_type} trend is {trend} with rate {t.get('rate_of_change', 0):.3f}",
                    confidence=t.get("confidence", 0.7),
                    timestamp=now
                ))
        
        # Evidence from predictions
        for gas_type, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None:
                evidence_list.append(Evidence(
                    source="prediction_service",
                    description=f"{gas_type} threshold expected in {crossing} min, growth rate {pred.get('growth_rate', 0):.3f}",
                    confidence=0.85,
                    timestamp=now
                ))
        
        # Evidence from correlations
        for corr in correlations:
            evidence_list.append(Evidence(
                source="correlation_service",
                description=corr.get("description", "Correlation detected"),
                confidence=0.8,
                timestamp=now
            ))
        
        # Evidence from explosion analysis
        for hazard in explosion_hazards:
            evidence_list.append(Evidence(
                source="explosion_service",
                description=hazard.get("description", "Hazard detected"),
                confidence=0.9,
                timestamp=now
            ))
        
        # Evidence from leak analysis
        for gas_type, analysis in leak_analyses.items():
            prob = analysis.get("probability", "LOW")
            if prob in ["MEDIUM", "HIGH", "CRITICAL"]:
                for reason in analysis.get("reasons", [])[:2]:
                    evidence_list.append(Evidence(
                        source="gas_leak_service",
                        description=f"{gas_type}: {reason}",
                        confidence=analysis.get("confidence", 0.7),
                        timestamp=now
                    ))
        
        # Evidence from sensor health
        health_status = sensor_health.get("status", "HEALTHY")
        if health_status != "HEALTHY":
            evidence_list.append(Evidence(
                source="validation_service",
                description=f"Sensor health: {health_status} - {sensor_health.get('message', '')}",
                confidence=0.95,
                timestamp=now
            ))
        
        # Sort by confidence descending, take top 15
        evidence_list.sort(key=lambda e: e.confidence, reverse=True)
        return evidence_list[:15]