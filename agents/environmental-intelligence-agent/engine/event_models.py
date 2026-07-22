"""
SENTINEL - Gas Intelligence Agent
Event models for standardized event communication.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from engine.enums import Severity


class Event(BaseModel):
    """
    Standardized event model for gas intelligence events.
    
    This schema is used across all SENTINEL agents for consistent
    event communication and logging.
    """
    
    event_id: str = Field(
        ...,
        description="Unique identifier for the event",
        examples=["evt-1234567890-abc123"]
    )
    
    event_name: str = Field(
        ...,
        description="Name/type of the event",
        max_length=200,
        examples=["METHANE_THRESHOLD_EXCEEDED", "OXYGEN_DEFICIT_DETECTED"]
    )
    
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp when the event occurred",
        examples=["2024-01-15T10:30:00Z"]
    )
    
    severity: Severity = Field(
        ...,
        description="Severity level of the event",
        examples=["WARNING"]
    )
    
    agent: str = Field(
        ...,
        description="Agent that generated the event",
        max_length=100,
        examples=["gas-intelligence-agent"]
    )
    
    zone: str = Field(
        ...,
        description="Industrial zone where the event occurred",
        max_length=100,
        examples=["refinery-section-3"]
    )
    
    description: str = Field(
        ...,
        description="Detailed description of the event",
        max_length=2000,
        examples=["Methane concentration exceeded threshold of 1000 ppm"]
    )
    
    recommended_action: Optional[str] = Field(
        None,
        description="Recommended action to address the event",
        max_length=1000,
        examples=["Evacuate zone and activate ventilation system"]
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata associated with the event",
        examples=[{"sensor_id": "sensor-123", "reading_value": 1250.5}]
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "evt-1234567890-abc123",
                    "event_name": "METHANE_THRESHOLD_EXCEEDED",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "severity": "WARNING",
                    "agent": "gas-intelligence-agent",
                    "zone": "refinery-section-3",
                    "description": "Methane concentration exceeded threshold of 1000 ppm. Current reading: 1250.5 ppm",
                    "recommended_action": "Evacuate zone and activate ventilation system",
                    "metadata": {
                        "sensor_id": "sensor-123",
                        "reading_value": 1250.5,
                        "threshold": 1000.0
                    }
                }
            ]
        }
    }


class EventBatch(BaseModel):
    """
    Batch of events for bulk operations.
    """
    
    events: list[Event] = Field(
        ...,
        description="List of events",
        min_length=1,
        max_length=1000
    )
    
    batch_id: Optional[str] = Field(
        None,
        description="Optional batch identifier",
        examples=["batch-20240115-001"]
    )