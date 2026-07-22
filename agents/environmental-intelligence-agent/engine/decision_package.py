"""
SENTINEL - Gas Intelligence Agent
Industrial Decision Package - Standard output for all SENTINEL agents.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class Evidence:
    """Structured evidence for a single decision factor."""
    source: str
    description: str
    confidence: float
    timestamp: Optional[datetime] = None


@dataclass
class TimelineEvent:
    """Predicted timeline event."""
    time_label: str
    time_seconds: int
    event: str
    severity: str
    confidence: float


@dataclass
class Decision:
    """Structured operational decision for downstream agents."""
    recommended_action: str = ""
    priority: str = "MEDIUM"
    urgency: str = "LOW"
    confidence: float = 0.0
    reason: str = ""


@dataclass
class SensorReliability:
    """Sensor reliability assessment."""
    sensor_id: str
    reliability_score: float
    confidence: float
    stability: str
    calibration_needed: bool
    communication_quality: str
    diagnostics: Dict[str, Any]


@dataclass
class SelfDiagnostics:
    """Service self-diagnostics."""
    module_health: Dict[str, str]
    history_buffer_usage: float
    prediction_engine_status: str
    validation_status: str
    internal_errors: List[str]
    warnings: List[str]
    uptime_seconds: float


@dataclass
class AuditRecord:
    """Audit trail record for a single analysis."""
    analysis_id: str
    timestamp: datetime
    zone: str
    plant: str
    equipment: str
    input_summary: Dict[str, Any]
    decision_summary: str
    evidence_summary: List[str]
    recommendations: List[str]
    risk_score: float
    prediction: Dict[str, Any]
    processing_time_ms: float
    agent_version: str


@dataclass
class Decision:
    """Structured decision for the Response Agent."""
    recommended_action: str
    priority: str
    urgency: str
    confidence: float
    reason: str


@dataclass
class IndustrialDecisionPackage:
    """
    Standard output object for all SENTINEL agents.
    
    This is the unified response that GasAgent produces,
    and that other agents/Orchestrator consume without transformation.
    """
    
    # Agent identity
    agent: str = "gas-intelligence-agent"
    agent_version: str = "1.0.0"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Location
    zone: str = ""
    plant: str = ""
    equipment: str = ""
    
    # Core risk assessment
    status: str = "SUCCESS"
    risk_score: float = 0.0
    confidence: float = 0.0
    severity: str = "NORMAL"
    processing_time_ms: float = 0.0
    
    # Per-gas analysis
    current_status: Dict[str, Any] = field(default_factory=dict)
    trend: Dict[str, Any] = field(default_factory=dict)
    gas_behaviour: Dict[str, str] = field(default_factory=dict)
    
    # Predictive analysis
    prediction: Dict[str, Any] = field(default_factory=dict)
    timeline: List[TimelineEvent] = field(default_factory=list)
    threshold_info: Dict[str, Any] = field(default_factory=dict)
    correlation: Dict[str, Any] = field(default_factory=dict)
    
    # Specialized analysis
    leak_analysis: Dict[str, Any] = field(default_factory=dict)
    explosion_probability: str = "LOW"
    explosion_assessment: Dict[str, Any] = field(default_factory=dict)
    historical_statistics: Dict[str, Any] = field(default_factory=dict)
    sensor_health: Dict[str, Any] = field(default_factory=dict)
    sensor_reliability: List[SensorReliability] = field(default_factory=list)
    
    # Risk factors and evidence
    risk_factors: Dict[str, float] = field(default_factory=dict)
    evidence: List[Evidence] = field(default_factory=list)
    
    # Decision
    decision: Optional[Decision] = None
    decision_reason: str = ""
    decision_urgency: str = "LOW"
    decision_confidence: float = 0.0
    
    # Actions
    events: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Summary
    summary: str = ""
    
    # Audit and diagnostics
    audit: Optional[AuditRecord] = None
    diagnostics: Optional[SelfDiagnostics] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    decision_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize package to dictionary for API response."""
        result = {
            "agent": self.agent,
            "agent_version": self.agent_version,
            "timestamp": self.timestamp.isoformat(),
            "zone": self.zone,
            "plant": self.plant,
            "equipment": self.equipment,
            "status": self.status,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "severity": self.severity,
            "processing_time_ms": self.processing_time_ms,
            "current_status": self.current_status,
            "trend": self.trend,
            "gas_behaviour": self.gas_behaviour,
            "prediction": self.prediction,
            "timeline": [{
                "time_label": t.time_label,
                "time_seconds": t.time_seconds,
                "event": t.event,
                "severity": t.severity,
                "confidence": t.confidence
            } for t in self.timeline],
            "threshold_info": self.threshold_info,
            "correlation": self.correlation,
            "leak_analysis": self.leak_analysis,
            "explosion_probability": self.explosion_probability,
            "explosion_assessment": self.explosion_assessment,
            "historical_statistics": self.historical_statistics,
            "sensor_health": self.sensor_health,
            "sensor_reliability": [{
                "sensor_id": s.sensor_id,
                "reliability_score": s.reliability_score,
                "confidence": s.confidence,
                "stability": s.stability,
                "calibration_needed": s.calibration_needed,
                "communication_quality": s.communication_quality,
                "diagnostics": s.diagnostics
            } for s in self.sensor_reliability],
            "risk_factors": self.risk_factors,
            "evidence": [{
                "source": e.source,
                "description": e.description,
                "confidence": e.confidence,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None
            } for e in self.evidence],
            "decision": {
                "recommended_action": self.decision.recommended_action,
                "priority": self.decision.priority,
                "urgency": self.decision.urgency,
                "confidence": self.decision.confidence,
                "reason": self.decision.reason,
            } if self.decision else None,
            "decision_reason": self.decision_reason,
            "decision_urgency": self.decision_urgency,
            "decision_confidence": self.decision_confidence,
            "events": self.events,
            "recommendations": self.recommendations,
            "summary": self.summary,
            "audit": {
                "analysis_id": self.audit.analysis_id,
                "timestamp": self.audit.timestamp.isoformat(),
                "zone": self.audit.zone,
                "plant": self.audit.plant,
                "equipment": self.audit.equipment,
                "input_summary": self.audit.input_summary,
                "decision_summary": self.audit.decision_summary,
                "evidence_summary": self.audit.evidence_summary,
                "recommendations": self.audit.recommendations,
                "risk_score": self.audit.risk_score,
                "prediction": self.audit.prediction,
                "processing_time_ms": self.audit.processing_time_ms,
                "agent_version": self.audit.agent_version
            } if self.audit else None,
            "diagnostics": {
                "module_health": self.diagnostics.module_health,
                "history_buffer_usage": self.diagnostics.history_buffer_usage,
                "prediction_engine_status": self.diagnostics.prediction_engine_status,
                "validation_status": self.diagnostics.validation_status,
                "internal_errors": self.diagnostics.internal_errors,
                "warnings": self.diagnostics.warnings,
                "uptime_seconds": self.diagnostics.uptime_seconds
            } if self.diagnostics else None,
            "metadata": self.metadata,
            "decision_metadata": self.decision_metadata
        }
        return result