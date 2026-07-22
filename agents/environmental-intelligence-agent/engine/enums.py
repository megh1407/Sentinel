"""
SENTINEL - Gas Intelligence Agent
Enumerations for standardized values across the system.
"""

from enum import Enum


class Severity(str, Enum):
    """
    Event severity levels for gas intelligence events.
    
    Follows industrial safety standards for incident classification.
    """
    NORMAL = "NORMAL"
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Trend(str, Enum):
    """
    Trend directions for gas concentration analysis.
    
    Used for temporal analysis of sensor readings.
    """
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    RAPID_INCREASE = "RAPID_INCREASE"
    DECREASING = "DECREASING"
    RAPID_DECREASE = "RAPID_DECREASE"


class SensorHealth(str, Enum):
    """
    Sensor health status indicators.
    
    Represents the operational state of gas sensors.
    """
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"


class GasType(str, Enum):
    """
    Types of gases monitored by the system.
    
    Standard industrial gas types for safety monitoring.
    """
    METHANE = "methane"
    CARBON_MONOXIDE = "carbon_monoxide"
    HYDROGEN_SULFIDE = "hydrogen_sulfide"
    OXYGEN = "oxygen"
    VOC = "voc"
    AMMONIA = "ammonia"


class EnvironmentalFactor(str, Enum):
    """
    Environmental factors monitored alongside gas concentrations.
    """
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"


class AgentStatus(str, Enum):
    """
    Overall agent processing status.
    """
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"
    PROCESSING = "PROCESSING"


class GasBehaviour(str, Enum):
    """Industrial gas behaviour classifications."""
    STABLE = "Stable"
    ACCUMULATING = "Accumulating"
    DILUTING = "Diluting"
    LEAKING = "Leaking"
    RAPID_BUILDUP = "Rapid Build-up"
    INTERMITTENT_RELEASE = "Intermittent Release"
    CONTINUOUS_RELEASE = "Continuous Release"


class LeakProbability(str, Enum):
    """Gas leak probability levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExplosionProbability(str, Enum):
    """Explosion probability levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SensorDiagnostic(str, Enum):
    """Detailed sensor diagnostic states."""
    HEALTHY = "Healthy"
    WARNING = "Warning"
    FAULT = "Fault"
    OFFLINE = "Offline"
    CALIBRATION_REQUIRED = "Calibration Required"
    SENSOR_DRIFT = "Sensor Drift"
    COMMUNICATION_DELAY = "Communication Delay"
    STUCK_SENSOR = "Stuck Sensor"


class EventType(str, Enum):
    """Supported industrial event types."""
    RAPID_GAS_RISE = "RapidGasRiseDetected"
    THRESHOLD_PREDICTION = "ThresholdPrediction"
    GAS_LEAK_SUSPECTED = "GasLeakSuspected"
    EXPLOSION_RISK = "ExplosionRiskDetected"
    TOXIC_ATMOSPHERE = "ToxicAtmosphereDetected"
    CONFINED_SPACE_HAZARD = "ConfinedSpaceHazard"
    FIRE_RISK = "FireRiskDetected"
    SENSOR_FAILURE = "SensorFailureDetected"
    MULTIPLE_GAS_HAZARD = "MultipleGasHazardDetected"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    IMMEDIATE = "IMMEDIATE"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
