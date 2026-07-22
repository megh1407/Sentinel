"""
SENTINEL - Gas Intelligence Agent
Decision engine for generating structured decisions.
"""

from typing import Dict, Any, List
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class DecisionService:
    """
    Generates structured decisions for the Response Agent.
    
    Output: decision_urgency, decision_confidence, decision_reason
    """
    
    def __init__(self) -> None:
        logger.info("DecisionService initialized")
    
    async def generate_decision(
        self,
        risk_score: float,
        severity: str,
        recommendations: List[str],
        evidence_count: int
    ) -> Dict[str, Any]:
        """Generate structured decision."""
        # Urgency
        if risk_score >= 70:
            urgency = "IMMEDIATE"
        elif risk_score >= 40:
            urgency = "HIGH"
        elif risk_score >= 20:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"
        
        # Confidence based on evidence volume
        confidence = round(min(1.0, 0.5 + evidence_count * 0.03), 2)
        
        # Reason
        if severity in ["CRITICAL", "HIGH"]:
            reason = f"Risk score {risk_score:.0f} with {severity} severity requires immediate action"
        elif urgency == "IMMEDIATE":
            reason = f"Risk score {risk_score:.0f} requires immediate attention"
        else:
            reason = f"Risk score {risk_score:.0f} - monitoring recommended"
        
        return {
            "urgency": urgency,
            "confidence": confidence,
            "reason": reason,
            "evidence_count": evidence_count
        }