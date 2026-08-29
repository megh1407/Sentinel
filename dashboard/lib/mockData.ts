import {
  ZoneRecord,
  ZoneState,
  ZoneAnomalyDetected,
  SiteState,
  FeedItem,
} from "./contracts";

/**
 * DEMO / SIMULATED DATA SOURCE
 * ----------------------------
 * This module stands in for the real backend-facing API client described
 * in the master prompt (Section 16-17: API client -> query layer -> view
 * models -> UI). It is the ONLY place demo data is fabricated.
 *
 * `state` and `anomalies` on each ZoneRecord are shaped exactly like the
 * real ZoneState / ZoneAnomalyDetected models zone_intelligence_agent
 * actually produces -- swapping this module for a real fetch() against
 * a future dashboard-service API is a mechanical change, not a rewrite.
 *
 * `environment`, `permits`, `workers`, `riskScore` are shaped from the
 * documented-but-unimplemented agent-contract schemas (see contracts.ts
 * header). They are clearly labeled SIMULATED everywhere they render.
 */

const now = () => new Date().toISOString();
const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

function zoneState(overrides: Partial<ZoneState> & { zone_id: string }): ZoneState {
  return {
    site_id: "SITE-01",
    current_risk_level: "LOW",
    active_permit_ids: [],
    active_permit_types: {},
    occupancy_count: 0,
    active_sensor_alert_ids: [],
    active_equipment_risk_ids: [],
    recent_incident_count: 0,
    pending_critical_maintenance_asset_ids: [],
    stale_sensor_ids: [],
    last_updated: now(),
    is_stale: false,
    ...overrides,
  };
}

function anomaly(
  zoneId: string,
  partial: Partial<ZoneAnomalyDetected> & { anomaly_id: string }
): ZoneAnomalyDetected {
  return {
    zone_id: zoneId,
    anomaly_type: "ENVIRONMENTAL_HAZARD",
    severity: "MEDIUM",
    event_timestamp: now(),
    explanation: {
      summary: "",
      confidence: { value: 0.8, derivation: "RULE_BASED" },
      evidence: [],
      reasoning_steps: [],
      risk_contributors: [],
      generated_at: now(),
    },
    ...partial,
  };
}

// ---- Zone A: the flagship compound-risk scenario from the spec -----------

const zoneA: ZoneRecord = {
  zoneId: "ZONE-A",
  displayName: "Zone A — Cracking Unit",
  x: 0,
  y: 0,
  state: zoneState({
    zone_id: "ZONE-A",
    current_risk_level: "CRITICAL",
    active_permit_ids: ["PMT-4471"],
    active_permit_types: { "PMT-4471": "hot_work" },
    occupancy_count: 18,
    active_sensor_alert_ids: ["SEN-CO-12", "SEN-CO-13"],
    recent_incident_count: 1,
  }),
  anomalies: [
    anomaly("ZONE-A", {
      anomaly_id: "ANM-9001",
      anomaly_type: "ZONE_HEALTH_DEGRADED",
      severity: "CRITICAL",
      event_timestamp: minutesAgo(4),
      explanation: {
        summary:
          "Elevated CO conditions are coinciding with active hot-work activity while workers are present in the zone.",
        confidence: { value: 0.91, derivation: "COMPOSITE" },
        evidence: [
          {
            source_event_id: "sen-evt-88213",
            source_type: "SensorEvent",
            description: "CO reading 112 ppm, above 100 ppm threshold, rising over 15 min",
            weight: 0.4,
            timestamp: minutesAgo(4),
          },
          {
            source_event_id: "pmt-evt-4471",
            source_type: "PermitEvent",
            description: "Hot-work permit PMT-4471 active in Zone A since 09:00",
            weight: 0.3,
            timestamp: minutesAgo(180),
          },
          {
            source_event_id: "wkr-evt-30442",
            source_type: "WorkerEvent",
            description: "18 workers currently present in Zone A",
            weight: 0.2,
            timestamp: minutesAgo(2),
          },
          {
            source_event_id: "ppe-evt-77120",
            source_type: "WorkerEvent",
            description: "PPE violation detected for Worker 104 (helmet not detected)",
            weight: 0.1,
            timestamp: minutesAgo(6),
          },
        ],
        reasoning_steps: [
          "CO concentration crossed the configured threshold for the first time this shift.",
          "An active hot-work permit was already open in the same zone.",
          "Worker presence in the zone means exposure is not hypothetical.",
          "A concurrent PPE violation removes a layer of protection during the exposure window.",
        ],
        risk_contributors: [
          { factor_name: "environmental_hazard", contribution_score: 38, description: "CO rising past threshold" },
          { factor_name: "active_hot_work", contribution_score: 27, description: "Hot-work permit active" },
          { factor_name: "worker_presence", contribution_score: 20, description: "18 workers in zone" },
          { factor_name: "ppe_violation", contribution_score: 15, description: "Helmet violation, Worker 104" },
        ],
        generated_at: minutesAgo(4),
      },
    }),
  ],
  environment: {
    zone_id: "ZONE-A",
    risk_score: 82,
    confidence: 0.88,
    hazards: [
      { hazard_type: "toxic_gas", label: "CO", measured_value: 112, unit: "ppm", threshold_ppm: 100, threshold_breach: true, trend: "rising", sensor_ids: ["SEN-CO-12"] },
      { hazard_type: "toxic_gas", label: "H\u2082S", measured_value: 8, unit: "ppm", threshold_ppm: 10, threshold_breach: false, trend: "stable", sensor_ids: ["SEN-H2S-04"] },
      { hazard_type: "oxygen_deficiency", label: "O\u2082", measured_value: 20.5, unit: "%", threshold_ppm: 19.5, threshold_breach: false, trend: "stable", sensor_ids: ["SEN-O2-02"] },
    ],
    evacuation_required: false,
    recommendations: ["Suspend hot-work permit pending CO recheck", "Increase ventilation in Zone A"],
    analyzed_at: minutesAgo(3),
  },
  permits: [
    {
      permit_id: "PMT-4471",
      permit_type: "Hot Work",
      zone_id: "ZONE-A",
      status: "active",
      valid_from: "09:00",
      valid_to: "17:00",
      permit_risk_level: "high",
      risk_score: 74,
      confidence: 0.82,
      conflicts: [],
      zone_compatibility: false,
      recommendations: ["Current environmental conditions may conflict with the active work activity."],
      analyzed_at: minutesAgo(3),
    },
    {
      permit_id: "PMT-4488",
      permit_type: "Confined Space",
      zone_id: "ZONE-A",
      status: "pending",
      valid_from: "13:00",
      valid_to: "16:00",
      permit_risk_level: "elevated",
      risk_score: 55,
      confidence: 0.7,
      conflicts: [{ conflicting_permit_id: "PMT-4471", conflict_type: "hot_work_confined_space", severity: "warning" }],
      zone_compatibility: false,
      recommendations: ["Review against active hot-work permit before approval."],
      analyzed_at: minutesAgo(3),
    },
  ],
  workers: [
    {
      worker_id: "WKR-104",
      zone_id: "ZONE-A",
      risk_score: 68,
      confidence: 0.85,
      safety_status: "at_risk",
      ppe_compliance: 0.66,
      ppe_violations: ["helmet_missing"],
      zone_clearance: true,
      proximity_alerts: [],
      analyzed_at: minutesAgo(6),
    },
  ],
  riskScore: {
    risk_id: "RSK-55210",
    zone_id: "ZONE-A",
    score: 87,
    severity: "critical",
    contributors: [
      { agent: "environmental_intelligence_agent", factor: "co_threshold_breach", weight: 0.35, score: 82, evidence: ["sen-evt-88213"] },
      { agent: "permit_intelligence_agent", factor: "hot_work_active", weight: 0.3, score: 74, evidence: ["pmt-evt-4471"] },
      { agent: "worker_safety_agent", factor: "ppe_violation", weight: 0.2, score: 68, evidence: ["ppe-evt-77120"] },
      { agent: "zone_intelligence_agent", factor: "occupancy_in_hazard", weight: 0.15, score: 60, evidence: ["wkr-evt-30442"] },
    ],
    explanation_summary:
      "The current risk is elevated because an environmental hazard overlaps with active work activity and worker exposure.",
    computed_at: minutesAgo(3),
  },
};

const zoneB: ZoneRecord = {
  zoneId: "ZONE-B",
  displayName: "Zone B — Tank Farm",
  x: 1,
  y: 0,
  state: zoneState({ zone_id: "ZONE-B", current_risk_level: "LOW", occupancy_count: 3 }),
  anomalies: [],
  environment: {
    zone_id: "ZONE-B",
    risk_score: 12,
    confidence: 0.9,
    hazards: [
      { hazard_type: "flammable_gas", label: "VOC", measured_value: 4, unit: "ppm", threshold_ppm: 50, threshold_breach: false, trend: "stable", sensor_ids: ["SEN-VOC-21"] },
    ],
    evacuation_required: false,
    recommendations: [],
    analyzed_at: minutesAgo(5),
  },
  permits: [],
  workers: [],
  riskScore: {
    risk_id: "RSK-55211",
    zone_id: "ZONE-B",
    score: 12,
    severity: "negligible",
    contributors: [],
    explanation_summary: "No active hazards or elevated signals in this zone.",
    computed_at: minutesAgo(5),
  },
};

const zoneC: ZoneRecord = {
  zoneId: "ZONE-C",
  displayName: "Zone C — Compressor House",
  x: 0,
  y: 1,
  state: zoneState({
    zone_id: "ZONE-C",
    current_risk_level: "HIGH",
    occupancy_count: 6,
    active_equipment_risk_ids: ["EQP-3301"],
    pending_critical_maintenance_asset_ids: ["EQP-3301"],
  }),
  anomalies: [
    anomaly("ZONE-C", {
      anomaly_id: "ANM-9002",
      anomaly_type: "ZONE_HEALTH_DEGRADED",
      severity: "HIGH",
      event_timestamp: minutesAgo(22),
      explanation: {
        summary: "Critical maintenance is pending on compressor EQP-3301 while workers remain present.",
        confidence: { value: 0.76, derivation: "RULE_BASED" },
        evidence: [
          {
            source_event_id: "mnt-evt-1187",
            source_type: "MaintenanceRequired",
            description: "EQP-3301 flagged for critical-urgency maintenance",
            weight: 0.6,
            timestamp: minutesAgo(40),
          },
          {
            source_event_id: "wkr-evt-30510",
            source_type: "WorkerEvent",
            description: "6 workers present in Zone C",
            weight: 0.4,
            timestamp: minutesAgo(5),
          },
        ],
        reasoning_steps: [
          "Equipment health degraded to critical-urgency maintenance status.",
          "Workers remain present in the same zone as the flagged equipment.",
        ],
        risk_contributors: [
          { factor_name: "equipment_health", contribution_score: 45, description: "Critical maintenance pending" },
          { factor_name: "worker_presence", contribution_score: 25, description: "6 workers in zone" },
        ],
        generated_at: minutesAgo(22),
      },
    }),
  ],
  environment: null,
  permits: [],
  workers: [],
  riskScore: {
    risk_id: "RSK-55212",
    zone_id: "ZONE-C",
    score: 63,
    severity: "high",
    contributors: [
      { agent: "maintenance_intelligence_agent", factor: "critical_maintenance_pending", weight: 0.6, score: 70, evidence: ["mnt-evt-1187"] },
    ],
    explanation_summary: "Equipment health risk compounding with sustained worker presence.",
    computed_at: minutesAgo(22),
  },
};

const zoneD: ZoneRecord = {
  zoneId: "ZONE-D",
  displayName: "Zone D — Warehouse",
  x: 1,
  y: 1,
  state: zoneState({ zone_id: "ZONE-D", current_risk_level: "LOW", occupancy_count: 9 }),
  anomalies: [],
  environment: null,
  permits: [],
  workers: [],
  riskScore: {
    risk_id: "RSK-55213",
    zone_id: "ZONE-D",
    score: 8,
    severity: "negligible",
    contributors: [],
    explanation_summary: "No active hazards or elevated signals in this zone.",
    computed_at: minutesAgo(8),
  },
};

const zoneE: ZoneRecord = {
  zoneId: "ZONE-E",
  displayName: "Zone E — Loading Dock",
  x: 2,
  y: 0,
  state: zoneState({
    zone_id: "ZONE-E",
    current_risk_level: "MEDIUM",
    occupancy_count: 11,
    stale_sensor_ids: ["SEN-TMP-09"],
  }),
  anomalies: [
    anomaly("ZONE-E", {
      anomaly_id: "ANM-9003",
      anomaly_type: "MISSING_SENSOR_DATA",
      severity: "LOW",
      event_timestamp: minutesAgo(35),
      explanation: {
        summary: "Temperature sensor SEN-TMP-09 has not reported in over the configured staleness window.",
        confidence: { value: 0.6, derivation: "RULE_BASED" },
        evidence: [
          { source_event_id: "sen-evt-90012", source_type: "SensorEvent", description: "Last reading 41 minutes ago", weight: 1, timestamp: minutesAgo(41) },
        ],
        reasoning_steps: ["Sensor last-seen timestamp exceeded the staleness threshold."],
        risk_contributors: [{ factor_name: "sensor_staleness", contribution_score: 10, description: "Stale temperature sensor" }],
        generated_at: minutesAgo(35),
      },
    }),
  ],
  environment: null,
  permits: [],
  workers: [],
  riskScore: {
    risk_id: "RSK-55214",
    zone_id: "ZONE-E",
    score: 28,
    severity: "low",
    contributors: [],
    explanation_summary: "Best-effort signal only — one sensor reporting stale data.",
    computed_at: minutesAgo(35),
  },
};

export const zones: ZoneRecord[] = [zoneA, zoneB, zoneC, zoneD, zoneE];

export function getZone(zoneId: string): ZoneRecord | undefined {
  return zones.find((z) => z.zoneId === zoneId);
}

export const siteState: SiteState = {
  site_id: "SITE-01",
  overall_state: "elevated",
  zone_summary: { safe: 2, watch: 1, warning: 1, danger: 1, evacuate: 0, lockdown: 0 },
  total_workers: zones.reduce((sum, z) => sum + z.state.occupancy_count, 0),
  highest_risk_zone: "ZONE-A",
  highest_risk_score: 87,
  active_incidents: 1,
  changed_at: minutesAgo(3),
};

export const feed: FeedItem[] = [
  { id: "f1", zoneId: "ZONE-A", message: "Compound risk detected in Zone A", timestamp: minutesAgo(3), source: "simulated", severity: "CRITICAL" },
  { id: "f2", zoneId: "ZONE-A", message: "PPE violation detected — Zone A", timestamp: minutesAgo(6), source: "real", severity: "HIGH" },
  { id: "f3", zoneId: "ZONE-A", message: "Gas conditions changed in Zone A (CO rising)", timestamp: minutesAgo(4), source: "simulated", severity: "CRITICAL" },
  { id: "f4", zoneId: "ZONE-A", message: "Hot-work permit became active in Zone A", timestamp: minutesAgo(180), source: "simulated", severity: "INFO" },
  { id: "f5", zoneId: "ZONE-C", message: "Zone C risk increased — equipment health degraded", timestamp: minutesAgo(22), source: "real", severity: "HIGH" },
  { id: "f6", zoneId: "ZONE-E", message: "Sensor SEN-TMP-09 stopped reporting in Zone E", timestamp: minutesAgo(35), source: "real", severity: "LOW" },
];
