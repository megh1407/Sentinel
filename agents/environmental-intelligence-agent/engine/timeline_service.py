"""
SENTINEL - Gas Intelligence Agent
Timeline prediction service for generating structured event timelines.
"""

from typing import Dict, Any, List, Optional
from engine.decision_package import TimelineEvent
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class TimelineService:
    """
    Generates structured timeline predictions.
    
    Instead of single threshold crossing time, generates:
    30s: Current Status
    2min: Expected Warning
    5min: Expected Critical
    """
    
    def __init__(self) -> None:
        """Initialize timeline service."""
        logger.info("TimelineService initialized")
    
    async def generate_timeline(
        self,
        predictions: Dict[str, Any],
        risk_score: float,
        severity: str,
        threshold_violations: List[Dict[str, Any]]
    ) -> List[TimelineEvent]:
        """
        Generate timeline from prediction and risk data.
        
        Args:
            predictions: Prediction data per gas
            risk_score: Current risk score
            severity: Current severity
            threshold_violations: Active violations
            
        Returns:
            List[TimelineEvent]: Structured timeline
        """
        timeline: List[TimelineEvent] = []
        
        # Immediate (now)
        timeline.append(TimelineEvent(
            time_label="Current",
            time_seconds=0,
            event=f"Risk Score: {risk_score:.0f}/100, Severity: {severity}",
            severity=severity,
            confidence=0.95
        ))
        
        # Find nearest threshold crossing
        min_crossing = None
        crossing_gas = None
        for gas_type, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None and crossing > 0:
                if min_crossing is None or crossing < min_crossing:
                    min_crossing = crossing
                    crossing_gas = gas_type
        
        # 30 seconds: current trend
        if min_crossing and min_crossing > 0.5:
            timeline.append(TimelineEvent(
                time_label="30 seconds",
                time_seconds=30,
                event=f"{crossing_gas or 'Gas'} trending toward threshold",
                severity="ADVISORY",
                confidence=0.7
            ))
        
        # 2 minutes: expected warning
        if min_crossing and min_crossing <= 5:
            timeline.append(TimelineEvent(
                time_label="2 minutes",
                time_seconds=120,
                event=f"{crossing_gas or 'Gas'} expected at WARNING threshold",
                severity="WARNING",
                confidence=0.8
            ))
        
        # 5 minutes: expected critical
        if min_crossing and min_crossing <= 10:
            timeline.append(TimelineEvent(
                time_label="5 minutes",
                time_seconds=300,
                event=f"{crossing_gas or 'Gas'} expected at HIGH threshold",
                severity="HIGH",
                confidence=0.75
            ))
        
        # No threshold crossing predicted
        if min_crossing is None or min_crossing > 30:
            timeline.append(TimelineEvent(
                time_label="5 minutes",
                time_seconds=300,
                event="No significant changes predicted",
                severity="NORMAL",
                confidence=0.6
            ))
        
        return timeline