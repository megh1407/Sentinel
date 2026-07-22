"""Enumerations for risk classification, severity, and prioritization.

Every value here is drawn verbatim from an architecture document; this
module invents no new taxonomy of its own (Phase 2.4 §4, §5; Phase 2.5 §2).
"""

from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    """The platform's fixed, six-band severity vocabulary (Phase 1 §5.1)."""

    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"


class DecisionCategory(str, Enum):
    """`DecisionEngine`'s classification labels (Phase 2.4 §4.1).

    Every member is a classification/signal, never an executed action
    (Phase 2.4 §1.4's terminology reconciliation).
    """

    SAFE = "safe"
    WARNING = "warning"
    HIGH_RISK = "high_risk"
    CRITICAL_RISK = "critical_risk"
    EMERGENCY = "emergency"
    IMMEDIATE_SHUTDOWN_RECOMMENDED = "immediate_shutdown_recommended"
    EVACUATION_RECOMMENDED = "evacuation_recommended"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    COMPLIANCE_INVESTIGATION_FLAGGED = "compliance_investigation_flagged"
    MAINTENANCE_REQUIRED_FLAGGED = "maintenance_required_flagged"
    PERMIT_SUSPENSION_FLAGGED = "permit_suspension_flagged"
    WORKER_INTERVENTION_FLAGGED = "worker_intervention_flagged"


class RecommendationPriority(str, Enum):
    """Priority tiers a recommendation signal inherits (Phase 2.4 §5.3, §7.3)."""

    P0_IMMEDIATE = "P0"
    P1_URGENT = "P1"
    P2_ELEVATED = "P2"
    P3_STANDARD = "P3"
    P4_ROUTINE = "P4"


class RecommendationCategory(str, Enum):
    """Recommendation-signal categories (Phase 2.4 §7.2)."""

    PPE_RECOMMENDATION = "ppe_recommendation"
    PERMIT_SUSPENSION = "permit_suspension"
    EQUIPMENT_INSPECTION = "equipment_inspection"
    WORKER_EVACUATION = "worker_evacuation"
    MAINTENANCE_SCHEDULING = "maintenance_scheduling"
    COMPLIANCE_REVIEW = "compliance_review"


class RuleCategory(str, Enum):
    """Rule taxonomy (Phase 2.3 §8.1)."""

    WORKER_SAFETY = "worker_safety"
    PERMIT = "permit"
    EQUIPMENT = "equipment"
    ENVIRONMENTAL = "environmental"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    EMERGENCY = "emergency"
    SITE = "site"
    ZONE = "zone"
    ORGANIZATION = "organization"
    CUSTOM = "custom"


class RulePriority(str, Enum):
    """Rule execution priority (Phase 2.3 §9.1)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class CorrelationType(str, Enum):
    """The eleven supported correlation types (Phase 2.3 §4.1)."""

    WORKER_ZONE = "worker_zone"
    WORKER_EQUIPMENT = "worker_equipment"
    WORKER_PERMIT = "worker_permit"
    EQUIPMENT_SENSOR = "equipment_sensor"
    EQUIPMENT_MAINTENANCE = "equipment_maintenance"
    ZONE_NEIGHBOR_ZONE = "zone_neighbor_zone"
    PERMIT_GAS_LEVEL = "permit_gas_level"
    PERMIT_EQUIPMENT = "permit_equipment"
    INCIDENT_HISTORICAL_INCIDENT = "incident_historical_incident"
    MAINTENANCE_EQUIPMENT_FAILURE = "maintenance_equipment_failure"
    WORKER_EVACUATION_ROUTE = "worker_evacuation_route"


class HazardCategory(str, Enum):
    """Categories of physical hazard a sensor/zone reading may report."""

    TOXIC_GAS = "toxic_gas"
    FLAMMABLE_GAS = "flammable_gas"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    RADIATION = "radiation"
    STRUCTURAL = "structural"
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    CONFINED_SPACE = "confined_space"


class RiskCategory(str, Enum):
    """High-level category a `RiskContributor`/finding belongs to."""

    DIRECT = "direct"
    COMPOUND = "compound"
    PREDICTIVE = "predictive"
