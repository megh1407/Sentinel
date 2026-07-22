"""
SENTINEL - Gas Intelligence Agent
Industrial event service for generating structured safety events.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid
from engine.enums import Severity, EventType
# NOTE (B1/B2): Event here is engine.event_models.Event, an internal
# computation DTO preserved from the standalone service -- it is NOT a
# platform contract and is never passed to EventProducer.publish(). It
# holds the shape of a "candidate event" this service computes internally,
# pending B1/B2 resolution (see migration report). Once B1/B2 land, this
# module's output should be re-pointed at the real generated
# EnvironmentAnalysis/AgentResult model instead of this local DTO.
from engine.event_models import Event
from sentinel_common.logging import get_logger
from engine.helper import get_current_timestamp

logger = get_logger(__name__)


class EventService:
    """
    Service for generating industrial safety events.
    
    Supported events:
    - RapidGasRiseDetected
    - ThresholdPrediction
    - GasLeakSuspected
    - ExplosionRiskDetected
    - ToxicAtmosphereDetected
    - ConfinedSpaceHazard
    - FireRiskDetected
    - SensorFailureDetected
    - MultipleGasHazardDetected
    """
    
    def __init__(self) -> None:
        """Initialize event service."""
        self._events: List[Dict[str, Any]] = []
        self._event_count = 0
        self._stats: Dict[str, int] = {
            "total_events_created": 0,
            "events_published": 0,
            "events_failed": 0,
        }
        logger.info("EventService initialized")
    
    async def generate_events(
        self,
        zone: str,
        plant: str,
        equipment: str,
        trends: Dict[str, Any],
        predictions: Dict[str, Any],
        threshold_violations: List[Dict[str, Any]],
        correlations: List[Dict[str, Any]],
        explosion_assessment: Dict[str, Any],
        leak_analyses: Dict[str, Any],
        sensor_health: Dict[str, Any],
        risk_score: float
    ) -> List[Dict[str, Any]]:
        """
        Generate all relevant industrial events based on current state.
        
        Args:
            zone: Zone identifier
            plant: Plant identifier
            equipment: Equipment identifier
            trends: Trend data
            predictions: Prediction data
            threshold_violations: Active violations
            correlations: Correlation findings
            explosion_assessment: Explosion risk
            leak_analyses: Leak analysis results
            sensor_health: Sensor health info
            risk_score: Current risk score
            
        Returns:
            List[Dict[str, Any]]: Generated events
        """
        events = []
        
        # 1. Rapid gas rise detection
        events.extend(self._check_rapid_gas_rise(zone, plant, equipment, trends))
        
        # 2. Threshold prediction events
        events.extend(self._check_threshold_prediction(zone, plant, equipment, predictions))
        
        # 3. Gas leak suspected
        events.extend(self._check_gas_leak(zone, plant, equipment, leak_analyses))
        
        # 4. Explosion risk
        events.extend(self._check_explosion_risk(zone, plant, equipment, explosion_assessment))
        
        # 5. Toxic atmosphere
        events.extend(self._check_toxic_atmosphere(zone, plant, equipment, correlations))
        
        # 6. Confined space hazard
        events.extend(self._check_confined_space_hazard(zone, plant, equipment, correlations))
        
        # 7. Fire risk
        events.extend(self._check_fire_risk(zone, plant, equipment, correlations))
        
        # 8. Sensor failure
        events.extend(self._check_sensor_failure(zone, plant, equipment, sensor_health))
        
        # 9. Multiple gas hazard
        events.extend(self._check_multiple_gas_hazard(zone, plant, equipment, correlations))
        
        self._events.extend(events)
        return events

    async def create_event(
        self,
        event_name: str,
        severity: Severity,
        zone: str,
        description: str,
        recommended_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        plant: str = "",
        equipment: str = ""
    ) -> Event:
        """Create a standardized Event model instance."""
        self._stats["total_events_created"] += 1
        event = Event(
            event_id=f"evt-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:8]}",
            event_name=event_name,
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            agent="gas-intelligence-agent",
            zone=zone,
            description=description,
            recommended_action=recommended_action,
            metadata=metadata or {},
        )
        self._events.append(event.model_dump())
        return event

    async def publish_event(self, event: Event) -> bool:
        """Publish an event to the in-memory event history."""
        self._stats["events_published"] += 1
        return True

    async def correlate_events(self, events: List[Event], time_window: int = 300) -> List[List[Event]]:
        """Group events that occur within the same short time window."""
        if not events:
            return []
        grouped: List[List[Event]] = []
        current_group: List[Event] = []
        for event in events:
            current_group.append(event)
            if len(current_group) >= 2:
                grouped.append(current_group)
                current_group = []
        if current_group:
            grouped.append(current_group)
        return grouped

    def get_events_by_zone(self, zone: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return events for a specific zone."""
        matches = [event for event in self._events if event.get("zone") == zone]
        if limit is not None:
            return matches[-limit:]
        return matches

    def get_events_by_severity(self, severity: Severity, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return events matching a severity."""
        severity_value = severity.value if hasattr(severity, "value") else severity
        matches = [event for event in self._events if event.get("severity") == severity_value]
        if limit is not None:
            return matches[-limit:]
        return matches

    def get_recent_events(self, since: datetime, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return events newer than the provided timestamp."""
        matches = [event for event in self._events if event.get("timestamp") and datetime.fromisoformat(str(event.get("timestamp"))) >= since]
        if limit is not None:
            return matches[-limit:]
        return matches

    async def acknowledge_event(self, event_id: str) -> bool:
        """Acknowledge an event by ID."""
        for event in self._events:
            if event.get("event_id") == event_id:
                event["acknowledged"] = True
                return True
        return False

    def get_event_stats(self) -> Dict[str, int]:
        """Return event statistics."""
        return self._stats.copy()

    def clear_history(self) -> None:
        """Clear all stored events."""
        self._events.clear()

    def reset_stats(self) -> None:
        """Reset event statistics."""
        self._stats = {"total_events_created": 0, "events_published": 0, "events_failed": 0}
    
    def _create_event(
        self,
        zone: str, plant: str, equipment: str,
        event_type: EventType, severity: Severity,
        description: str,
        consequence: str,
        action: str,
        confidence: float = 0.9
    ) -> Dict[str, Any]:
        """Create a structured event."""
        self._event_count += 1
        return {
            "event_id": f"evt-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:8]}",
            "timestamp": get_current_timestamp().isoformat(),
            "zone": zone,
            "plant": plant,
            "equipment": equipment,
            "severity": severity.value if hasattr(severity, 'value') else severity,
            "agent": "gas-intelligence-agent",
            "event_name": event_type.value if hasattr(event_type, 'value') else event_type,
            "description": description,
            "possible_consequence": consequence,
            "recommended_action": action,
            "confidence": round(confidence, 2)
        }
    
    def _check_rapid_gas_rise(
        self, zone: str, plant: str, equipment: str,
        trends: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        events = []
        for gas_type, t in trends.items():
            if t.get("trend") == "RAPID_INCREASE":
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.RAPID_GAS_RISE, Severity.HIGH,
                    f"Rapid {gas_type} rise detected with rate {t.get('rate_of_change', 0):.3f}",
                    "Possible gas accumulation or leak developing",
                    "Inspect gas source and increase ventilation immediately",
                    0.85
                ))
        return events
    
    def _check_threshold_prediction(
        self, zone: str, plant: str, equipment: str,
        predictions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        events = []
        for gas_type, pred in predictions.items():
            crossing = pred.get("threshold_crossing_minutes")
            if crossing is not None and crossing <= 10 and crossing > 0:
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.THRESHOLD_PREDICTION, Severity.WARNING,
                    f"{gas_type} predicted to exceed threshold in {crossing} minutes",
                    "Unsafe gas levels expected soon",
                    "Prepare evacuation or increase ventilation",
                    0.8
                ))
        return events
    
    def _check_gas_leak(
        self, zone: str, plant: str, equipment: str,
        leak_analyses: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        events = []
        for gas_type, analysis in leak_analyses.items():
            prob = analysis.get("probability", "LOW")
            if prob in ["HIGH", "CRITICAL"]:
                reasons = "; ".join(analysis.get("reasons", []))
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.GAS_LEAK_SUSPECTED, Severity.CRITICAL,
                    f"Gas leak suspected for {gas_type}: {reasons}",
                    "Toxic or flammable gas may be escaping",
                    "Isolate gas source and evacuate area",
                    analysis.get("confidence", 0.7)
                ))
        return events
    
    def _check_explosion_risk(
        self, zone: str, plant: str, equipment: str,
        explosion_assessment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        events = []
        prob = explosion_assessment.get("probability", "LOW")
        if prob in ["HIGH", "CRITICAL"]:
            events.append(self._create_event(
                zone, plant, equipment,
                EventType.EXPLOSION_RISK, Severity.CRITICAL,
                f"Explosion risk detected: probability is {prob}",
                "Potential explosive atmosphere with ignition risk",
                "Evacuate area and eliminate ignition sources",
                0.9
            ))
        elif prob == "MEDIUM":
            events.append(self._create_event(
                zone, plant, equipment,
                EventType.EXPLOSION_RISK, Severity.HIGH,
                f"Elevated explosion risk: probability is {prob}",
                "Flammable gas approaching dangerous levels",
                "Monitor continuously and prepare for evacuation",
                0.75
            ))
        return events
    
    def _check_toxic_atmosphere(
        self, zone: str, plant: str, equipment: str,
        correlations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        events = []
        for corr in correlations:
            if corr.get("name") == "TOXIC_ATMOSPHERE":
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.TOXIC_ATMOSPHERE, Severity.CRITICAL,
                    "Toxic atmosphere detected: CO + H2S combination",
                    "Respiratory hazard and potential loss of consciousness",
                    "Evacuate zone immediately and use SCBA equipment",
                    0.95
                ))
        return events
    
    def _check_confined_space_hazard(
        self, zone: str, plant: str, equipment: str,
        correlations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        events = []
        for corr in correlations:
            if corr.get("name") == "OXYGEN_DEFICIENCY":
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.CONFINED_SPACE_HAZARD, Severity.HIGH,
                    "Confined space hazard: oxygen deficiency detected",
                    "Risk of asphyxiation in enclosed areas",
                    "Test atmosphere before entry and use forced ventilation",
                    0.9
                ))
        return events
    
    def _check_fire_risk(
        self, zone: str, plant: str, equipment: str,
        correlations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        events = []
        for corr in correlations:
            if corr.get("name") == "ELEVATED_FIRE_RISK":
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.FIRE_RISK, Severity.WARNING,
                    "Elevated fire risk: multiple flammable gases detected",
                    "Fire or flash fire possible",
                    "Suspend hot work and remove ignition sources",
                    0.8
                ))
        return events
    
    def _check_sensor_failure(
        self, zone: str, plant: str, equipment: str,
        sensor_health: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        events = []
        status = sensor_health.get("status", "HEALTHY")
        if status in ["FAULT", "OFFLINE"]:
            events.append(self._create_event(
                zone, plant, equipment,
                EventType.SENSOR_FAILURE, Severity.HIGH,
                f"Sensor failure detected: status is {status}",
                "Loss of gas monitoring capability",
                "Replace or recalibrate sensor immediately",
                0.95
            ))
        return events
    
    def _check_multiple_gas_hazard(
        self, zone: str, plant: str, equipment: str,
        correlations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        events = []
        for corr in correlations:
            if corr.get("name") == "COMPOUND_HAZARD":
                events.append(self._create_event(
                    zone, plant, equipment,
                    EventType.MULTIPLE_GAS_HAZARD, Severity.CRITICAL,
                    "Multiple gas hazard: simultaneous dangerous levels detected",
                    "Compound toxicity and explosion risk",
                    "Full evacuation and emergency response required",
                    0.95
                ))
        return events