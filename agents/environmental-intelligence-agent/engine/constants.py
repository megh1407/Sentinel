"""
SENTINEL - Gas Intelligence Agent
Application constants and configuration values.
"""

from typing import Dict, List

# Application Constants
APP_NAME = "SENTINEL - Gas Intelligence Agent"
AGENT_NAME = "gas-intelligence-agent"
AGENT_VERSION = "1.0.0"
API_VERSION = "v1"

# Gas Concentration Thresholds (ppm - parts per million)
GAS_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "methane": {
        "advisory": 500.0,
        "warning": 1000.0,
        "high": 5000.0,
        "critical": 10000.0,
        "lower_explosive_limit": 50000.0,
        "upper_explosive_limit": 150000.0
    },
    "carbon_monoxide": {
        "advisory": 15.0,
        "warning": 35.0,
        "high": 100.0,
        "critical": 400.0,
        "immediately_dangerous": 1200.0
    },
    "hydrogen_sulfide": {
        "advisory": 5.0,
        "warning": 10.0,
        "high": 20.0,
        "critical": 50.0,
        "immediately_dangerous": 100.0
    },
    "oxygen": {
        "deficiency_advisory": 19.5,
        "deficiency_warning": 19.0,
        "deficiency_critical": 16.0,
        "excess_advisory": 23.5,
        "excess_warning": 25.0,
        "normal_min": 19.5,
        "normal_max": 23.5
    },
    "voc": {
        "advisory": 200.0,
        "warning": 500.0,
        "high": 1000.0,
        "critical": 5000.0
    },
    "ammonia": {
        "advisory": 15.0,
        "warning": 25.0,
        "high": 50.0,
        "critical": 100.0,
        "immediately_dangerous": 300.0
    }
}

# Environmental Thresholds
ENVIRONMENTAL_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "temperature": {
        "cold_advisory": 10.0,
        "cold_warning": 0.0,
        "hot_advisory": 35.0,
        "hot_warning": 45.0,
        "hot_critical": 60.0,
        "normal_min": 15.0,
        "normal_max": 30.0
    },
    "humidity": {
        "low_advisory": 30.0,
        "low_warning": 20.0,
        "high_advisory": 70.0,
        "high_warning": 85.0,
        "high_critical": 95.0,
        "normal_min": 30.0,
        "normal_max": 70.0
    },
    "pressure": {
        "low_advisory": 12.0,
        "low_warning": 10.0,
        "high_advisory": 16.0,
        "high_warning": 18.0,
        "high_critical": 20.0,
        "normal_min": 13.0,
        "normal_max": 15.0
    }
}

# Risk Scoring Weights
RISK_WEIGHTS: Dict[str, float] = {
    "methane": 0.20,
    "carbon_monoxide": 0.20,
    "hydrogen_sulfide": 0.15,
    "oxygen": 0.10,
    "voc": 0.10,
    "ammonia": 0.10,
    "temperature": 0.05,
    "humidity": 0.05,
    "pressure": 0.05
}

# Event Names
EVENT_NAMES: Dict[str, str] = {
    "METHANE_THRESHOLD_EXCEEDED": "Methane concentration exceeded threshold",
    "CO_THRESHOLD_EXCEEDED": "Carbon Monoxide concentration exceeded threshold",
    "H2S_THRESHOLD_EXCEEDED": "Hydrogen Sulfide concentration exceeded threshold",
    "OXYGEN_DEFICIT": "Oxygen level below safe threshold",
    "OXYGEN_EXCESS": "Oxygen level above normal range",
    "VOC_THRESHOLD_EXCEEDED": "VOC concentration exceeded threshold",
    "AMMONIA_THRESHOLD_EXCEEDED": "Ammonia concentration exceeded threshold",
    "TEMPERATURE_HIGH": "Temperature above safe threshold",
    "TEMPERATURE_LOW": "Temperature below safe threshold",
    "HUMIDITY_HIGH": "Humidity above safe threshold",
    "HUMIDITY_LOW": "Humidity below safe threshold",
    "PRESSURE_HIGH": "Pressure above safe threshold",
    "PRESSURE_LOW": "Pressure below safe threshold",
    "SENSOR_FAULT": "Sensor fault detected",
    "SENSOR_OFFLINE": "Sensor offline",
    "MULTIPLE_ANOMALIES": "Multiple anomalies detected",
    "TREND_RAPID_INCREASE": "Rapid increasing trend detected",
    "TREND_RAPID_DECREASE": "Rapid decreasing trend detected",
    "PREDICTION_WARNING": "Predictive warning generated",
    "CORRELATION_DETECTED": "Correlated anomalies detected"
}

# Severity Descriptions
SEVERITY_DESCRIPTIONS: Dict[str, str] = {
    "NORMAL": "All parameters within normal range",
    "ADVISORY": "Minor deviation from normal, monitor closely",
    "WARNING": "Significant deviation, action may be required",
    "HIGH": "Critical threshold exceeded, immediate action required",
    "CRITICAL": "Dangerous conditions, evacuate and emergency response"
}

# Sensor Health Thresholds
SENSOR_HEALTH_THRESHOLDS: Dict[str, int] = {
    "data_quality_minimum": 80,
    "response_time_max_ms": 1000,
    "calibration_age_days": 90
}

# Prediction Parameters
PREDICTION_PARAMS: Dict[str, int] = {
    "window_size": 10,
    "horizon": 5,
    "min_data_points": 3,
    "confidence_threshold": 70
}

# Trend Detection Parameters
TREND_PARAMS: Dict[str, float] = {
    "stable_threshold": 0.1,
    "increasing_threshold": 0.3,
    "rapid_increase_threshold": 0.7,
    "decreasing_threshold": -0.3,
    "rapid_decrease_threshold": -0.7
}

# Correlation Parameters
CORRELATION_PARAMS: Dict[str, float] = {
    "min_correlation_coefficient": 0.7,
    "max_time_lag_seconds": 300,
    "min_events_for_correlation": 2
}

# Explosion Detection Parameters
EXPLOSION_PARAMS: Dict[str, float] = {
    "methane_lel_percentage": 5.0,
    "oxygen_deficiency_percentage": 19.5,
    "temperature_ignition_celsius": 537.0,
    "pressure_increase_factor": 1.5
}

# HTTP Status Codes
HTTP_STATUS: Dict[str, int] = {
    "OK": 200,
    "CREATED": 201,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "INTERNAL_ERROR": 500,
    "SERVICE_UNAVAILABLE": 503
}

# API Response Messages
RESPONSE_MESSAGES: Dict[str, str] = {
    "success": "Operation completed successfully",
    "created": "Resource created successfully",
    "updated": "Resource updated successfully",
    "deleted": "Resource deleted successfully",
    "validation_error": "Validation error occurred",
    "not_found": "Resource not found",
    "internal_error": "Internal server error",
    "service_unavailable": "Service temporarily unavailable"
}

# Data Retention
DATA_RETENTION: Dict[str, int] = {
    "history_days": 30,
    "events_days": 90,
    "logs_days": 30,
    "max_history_per_zone": 1000
}

# Unit Conversions
UNIT_CONVERSIONS: Dict[str, float] = {
    "ppm_to_mg_m3": 1.0,  # Placeholder, varies by gas
    "celsius_to_fahrenheit": 1.8,
    "psi_to_kpa": 6.895,
    "percent_to_decimal": 0.01
}

# Gas Molecular Weights (g/mol) for ppm to mg/m³ conversion
GAS_MOLECULAR_WEIGHTS: Dict[str, float] = {
    "methane": 16.04,
    "carbon_monoxide": 28.01,
    "hydrogen_sulfide": 34.08,
    "oxygen": 32.00,
    "voc": 58.08,  # Average for VOCs
    "ammonia": 17.03
}

# Standard Conditions
STANDARD_CONDITIONS: Dict[str, float] = {
    "temperature_celsius": 25.0,
    "pressure_kpa": 101.325,
    "molar_volume_liters": 24.45
}

# Time Constants (seconds)
TIME_CONSTANTS: Dict[str, int] = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800
}

# Regex Patterns
PATTERNS: Dict[str, str] = {
    "zone_name": r'^[a-zA-Z0-9\-_\s]+$',
    "event_id": r'^evt-\d+-[a-f0-9]+$',
    "batch_id": r'^batch-\d{14}-[a-f0-9]+$',
    "iso8601": r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
}

# Service Health Check Intervals (seconds)
HEALTH_CHECK_INTERVALS: Dict[str, int] = {
    "self": 30,
    "dependencies": 60,
    "external_services": 120
}

# Rate Limiting
RATE_LIMITS: Dict[str, int] = {
    "requests_per_minute": 100,
    "requests_per_hour": 1000,
    "burst_size": 50
}

# Supported Gas Types
SUPPORTED_GASES: List[str] = [
    "methane",
    "carbon_monoxide",
    "hydrogen_sulfide",
    "oxygen",
    "voc",
    "ammonia"
]

# Supported Environmental Factors
SUPPORTED_ENVIRONMENTAL_FACTORS: List[str] = [
    "temperature",
    "humidity",
    "pressure"
]

# All Supported Parameters
ALL_SUPPORTED_PARAMETERS: List[str] = SUPPORTED_GASES + SUPPORTED_ENVIRONMENTAL_FACTORS