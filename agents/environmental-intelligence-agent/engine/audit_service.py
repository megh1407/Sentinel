"""
SENTINEL - Gas Intelligence Agent
Audit trail service for recording every analysis.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
import uuid
from engine.decision_package import AuditRecord
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """
    Creates an audit trail record for every analysis.
    
    Captures: analysis_id, timestamp, zone, plant, equipment,
    input summary, decision summary, evidence, recommendations,
    risk score, prediction, processing time.
    """
    
    def __init__(self) -> None:
        self._audit_records: List[AuditRecord] = []
        logger.info("AuditService initialized")
    
    async def create_record(
        self,
        zone: str,
        plant: str,
        equipment: str,
        input_summary: Dict[str, Any],
        decision_summary: str,
        evidence_summary: List[str],
        recommendations: List[str],
        risk_score: float,
        prediction: Dict[str, Any],
        processing_time_ms: float
    ) -> AuditRecord:
        """Create an audit record for this analysis."""
        record = AuditRecord(
            analysis_id=f"audit-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc),
            zone=zone,
            plant=plant,
            equipment=equipment,
            input_summary=input_summary,
            decision_summary=decision_summary,
            evidence_summary=evidence_summary,
            recommendations=recommendations,
            risk_score=risk_score,
            prediction=prediction,
            processing_time_ms=round(processing_time_ms, 2),
            agent_version="1.0.0"
        )
        self._audit_records.append(record)
        
        # Keep only last 1000 audit records
        if len(self._audit_records) > 1000:
            self._audit_records = self._audit_records[-1000:]
        
        return record
    
    def get_recent_records(self, limit: int = 10) -> List[AuditRecord]:
        """Get recent audit records."""
        return self._audit_records[-limit:] if self._audit_records else []
    
    def clear_records(self) -> None:
        """Clear all audit records."""
        self._audit_records.clear()
        logger.debug("Audit records cleared")