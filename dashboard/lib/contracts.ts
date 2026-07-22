/**
 * Frontend-facing TypeScript mirrors of SENTINEL's backend contracts.
 *
 * Every field here traces to a specific file inspected in the repo audit:
 *   - ZoneState / ZoneAnomalyDetected / ExplanationObject / EvidenceItem /
 *     RiskContributor / ConfidenceScore -> sentinel_contracts/**, the
 *     generated Pydantic models actually produced by zone_intelligence_agent.
 *   - EnvironmentAnalysis / PermitAnalysis / WorkerAnalysis ->
 *     contracts/agent-contracts/v1/*.schema.json. As of the Phase 10
 *     integration (platform-services/api-gateway), all three ARE produced
 *     by real, running agents (Environmental/Permit/Worker Safety) and
 *     served over a real REST API -- see lib/api.ts. This comment
 *     previously said otherwise; that was stale documentation from before
 *     those agents' implementations were completed, not a current fact.
 *     RiskScore / SiteState still have no producing agent (Risk
 *     Orchestrator is out of scope) -- lib/api.ts derives SiteState from
 *     real per-zone data client-side and always leaves riskScore null.
 *     Marked `source: "simulated"` below only where still true.
 *
 * Do not add fields that aren't backed by one of the schema files above.
 */

export type DataSource = "real" | "simulated";

// ---- Real: zone_intelligence_agent ----------------------------------------

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "LOCKDOWN";

export type ZoneAnomalyType =
  | "OCCUPANCY_EXCEEDED"
  | "ENVIRONMENTAL_HAZARD"
  | "RESTRICTED_AREA_VIOLATION"
  | "ZONE_HEALTH_DEGRADED"
  | "PERMIT_CONFLICT"
  | "INCIDENT_FREQUENCY_EXCEEDED"
  | "REPEATED_ANOMALIES"
  | "RAPID_STATE_CHANGE"
  | "MISSING_SENSOR_DATA";

export type AnomalySeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface EvidenceItem {
  source_event_id: string;
  source_type: string;
  description: string;
  weight: number;
  timestamp: string;
}

export interface RiskContributor {
  factor_name: string;
  contribution_score: number;
  description: string;
  source_event_id?: string;
}

export interface ConfidenceScore {
  value: number;
  derivation: "RULE_BASED" | "MODEL_BASED" | "COMPOSITE";
}

export interface ExplanationObject {
  summary: string;
  confidence: ConfidenceScore;
  evidence: EvidenceItem[];
  reasoning_steps: string[];
  risk_contributors: RiskContributor[];
  generated_at: string;
}

export interface ZoneState {
  zone_id: string;
  site_id: string;
  current_risk_level: RiskLevel;
  active_permit_ids: string[];
  active_permit_types: Record<string, string>; // permit_id -> type
  occupancy_count: number;
  active_sensor_alert_ids: string[];
  active_equipment_risk_ids: string[];
  recent_incident_count: number;
  pending_critical_maintenance_asset_ids: string[];
  stale_sensor_ids: string[];
  last_updated: string;
  is_stale: boolean;
}

export interface ZoneAnomalyDetected {
  anomaly_id: string;
  zone_id: string;
  anomaly_type: ZoneAnomalyType;
  severity: AnomalySeverity;
  explanation: ExplanationObject;
  event_timestamp: string;
}

// ---- Simulated: shaped from contracts/agent-contracts/v1/*.schema.json ----
// (schema exists; no agent implementation produces this yet)

export type HazardType =
  | "flammable_gas"
  | "toxic_gas"
  | "oxygen_deficiency"
  | "high_temperature"
  | "high_pressure"
  | "chemical_exposure"
  | "radiation";

export interface HazardReading {
  hazard_type: HazardType;
  label: string;
  measured_value: number;
  unit: string;
  threshold_ppm?: number;
  threshold_breach: boolean;
  trend: "rising" | "stable" | "falling";
  sensor_ids: string[];
}

export interface EnvironmentAnalysis {
  zone_id: string;
  risk_score: number;
  confidence: number;
  hazards: HazardReading[];
  evacuation_required: boolean;
  recommendations: string[];
  analyzed_at: string;
}

export interface PermitConflict {
  conflicting_permit_id: string;
  conflict_type: string;
  severity: "advisory" | "warning" | "blocking";
}

export interface PermitAnalysis {
  permit_id: string;
  permit_type: string;
  zone_id: string;
  status: "active" | "pending" | "expired" | "revoked";
  valid_from: string;
  valid_to: string;
  permit_risk_level: "acceptable" | "elevated" | "high" | "unacceptable";
  risk_score: number;
  confidence: number;
  conflicts: PermitConflict[];
  zone_compatibility: boolean;
  recommendations: string[];
  analyzed_at: string;
}

export interface ProximityAlert {
  hazard_type: string;
  distance_m: number;
  safe_distance_m: number;
}

export interface WorkerAnalysis {
  worker_id: string;
  zone_id: string;
  risk_score: number;
  confidence: number;
  safety_status: "safe" | "at_risk" | "in_danger" | "unresponsive";
  ppe_compliance: number;
  ppe_violations: string[];
  zone_clearance: boolean;
  proximity_alerts: ProximityAlert[];
  analyzed_at: string;
}

export type RiskSeverity =
  | "negligible"
  | "low"
  | "moderate"
  | "high"
  | "critical"
  | "catastrophic";

export interface RiskContributorScore {
  agent: string;
  factor: string;
  weight: number;
  score: number;
  evidence: string[];
}

export interface RiskScore {
  risk_id: string;
  zone_id: string;
  score: number;
  severity: RiskSeverity;
  contributors: RiskContributorScore[];
  explanation_summary: string;
  computed_at: string;
}

export type PlantOverallState =
  | "normal"
  | "elevated"
  | "emergency"
  | "evacuating"
  | "shutdown"
  | "lockdown";

export interface SiteState {
  site_id: string;
  overall_state: PlantOverallState;
  zone_summary: Record<string, number>;
  total_workers: number;
  highest_risk_zone: string;
  highest_risk_score: number;
  active_incidents: number;
  changed_at: string;
}

// ---- Frontend-only composite: one zone's full picture ----

export interface ZoneRecord {
  zoneId: string;
  displayName: string;
  x: number; // heatmap grid position (frontend layout only, not backend data)
  y: number;
  state: ZoneState; // real
  anomalies: ZoneAnomalyDetected[]; // real
  environment: EnvironmentAnalysis | null; // simulated
  permits: PermitAnalysis[]; // simulated
  workers: WorkerAnalysis[]; // simulated
  riskScore: RiskScore | null; // simulated
}

export interface FeedItem {
  id: string;
  zoneId: string;
  message: string;
  timestamp: string;
  source: DataSource;
  severity: AnomalySeverity | "INFO";
}
