"""
SENTINEL - Gas Intelligence Agent
Sensor reliability and diagnostics service.
"""

from typing import Dict, Any, List
from engine.decision_package import SensorReliability
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class SensorReliabilityService:
    """
    Service for calculating sensor reliability, stability, and diagnostics.
    
    Provides: reliability score, confidence, stability, calibration recommendations.
    """
    
    def __init__(self) -> None:
        """Initialize sensor reliability service."""
        logger.info("SensorReliabilityService initialized")
    
    async def assess_reliability(
        self,
        sensor_id: str,
        sensor_health: Dict[str, Any],
        validation_stats: Dict[str, int]
    ) -> SensorReliability:
        """Calculate comprehensive sensor reliability."""
        status = sensor_health.get("status", "HEALTHY")
        
        # Base reliability score
        reliability_scores = {
            "HEALTHY": 0.95,
            "WARNING": 0.70,
            "FAULT": 0.35,
            "OFFLINE": 0.0
        }
        base_score = reliability_scores.get(status, 0.5)
        
        # Adjust based on validation history
        total = validation_stats.get("total_validations", 0)
        failed = validation_stats.get("failed_validations", 0)
        success_rate = 1.0 - (failed / max(total, 1))
        reliability = base_score * (0.7 + 0.3 * success_rate)
        reliability = round(max(0.0, min(1.0, reliability)), 3)
        
        # Confidence
        confidence = round(min(1.0, total / 100.0), 3) if total > 0 else 0.3
        
        # Stability classification
        if reliability >= 0.9:
            stability = "EXCELLENT"
        elif reliability >= 0.7:
            stability = "GOOD"
        elif reliability >= 0.4:
            stability = "FAIR"
        else:
            stability = "POOR"
        
        # Calibration need
        calibration_needed = reliability < 0.5 or status in ["FAULT", "OFFLINE"]
        
        # Communication quality
        if status == "OFFLINE":
            comm_quality = "NO_COMMUNICATION"
        elif status == "FAULT":
            comm_quality = "INTERMITTENT"
        elif failed > total * 0.1:
            comm_quality = "DEGRADED"
        else:
            comm_quality = "NORMAL"
        
        return SensorReliability(
            sensor_id=sensor_id,
            reliability_score=reliability,
            confidence=confidence,
            stability=stability,
            calibration_needed=calibration_needed,
            communication_quality=comm_quality,
            diagnostics={
                "status": status,
                "total_validations": total,
                "failed_validations": failed,
                "success_rate": round(success_rate, 3)
            }
        )