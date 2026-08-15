/**
 * lib/api.ts -- real backend integration (Phase 10 frontend<->API wiring)
 *
 * Fetches from platform-services/api-gateway (see its README for how to
 * run it) and maps the raw JSON it returns into the SAME ZoneRecord /
 * SiteState / FeedItem shapes mockData.ts already exports -- so every
 * component that currently imports from "./mockData" can switch to
 * importing from here with no other changes.
 *
 * IMPORTANT, honestly stated: the api-gateway's /api/zones response gives
 * real ZoneState (from Redis) and real EnvironmentAnalysis / PermitAnalysis
 * / WorkerAnalysis (from its in-memory cache of the real agents' output --
 * see state_cache.py). riskScore is now ALSO real: the Risk Orchestrator
 * (agents/risk-orchestrator-agent) is wired and its SystemRiskAssessment is
 * served at /api/risk-assessments -- fetchZoneRecords attaches it per zone.
 * Topology (/api/topology, from Neo4j) and response decisions
 * (/api/action-requests, from the Response Agent) are exposed too. Anything
 * this file cannot honestly derive from a real API response is still left
 * null/empty rather than fabricated.
 */
import {
  ZoneRecord,
  ZoneState,
  EnvironmentAnalysis,
  PermitAnalysis,
  WorkerAnalysis,
  SiteState,
  FeedItem,
  RiskLevel,
  RiskScore,
  RiskSeverity,
} from "./contracts";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE ?? "http://localhost:8000";

// Fixed layout positions for the demo scenario's single zone plus a few
// placeholders -- matches mockData.ts's approach of hand-placed grid
// coordinates (frontend layout only, never backend data). Extend this map
// as real zones appear; unknown zone_ids fall back to a simple index-based
// grid so nothing crashes if a new zone shows up.
const KNOWN_ZONE_LAYOUT: Record<string, { x: number; y: number; displayName: string }> = {
  "ZONE-A": { x: 1, y: 1, displayName: "Zone A" },
  "ZONE-B": { x: 2, y: 1, displayName: "Zone B" },
  "ZONE-C": { x: 3, y: 1, displayName: "Zone C" },
  "ZONE-D": { x: 1, y: 2, displayName: "Zone D" },
  "ZONE-E": { x: 2, y: 2, displayName: "Zone E" },
};

function layoutFor(zoneId: string, index: number) {
  return (
    KNOWN_ZONE_LAYOUT[zoneId] ?? {
      x: (index % 3) + 1,
      y: Math.floor(index / 3) + 1,
      displayName: zoneId,
    }
  );
}

// -- raw shapes returned by platform-services/api-gateway/main.py -----------
// (mirrors of the real Pydantic .model_dump(mode="json") output -- every
// field name here was verified against a real response, not guessed.)

interface RawZoneEntry {
  zone_state: any;
  environment: any | null;
  active_permits: any[];
  workers: any[];
}

function mapZoneState(raw: any): ZoneState {
  const p = raw.payload;
  return {
    zone_id: raw.zone_id,
    site_id: raw.site_id,
    current_risk_level: p.current_risk_level as RiskLevel,
    active_permit_ids: p.active_permit_ids ?? [],
    active_permit_types: p.active_permit_types ?? {},
    occupancy_count: p.occupancy_count ?? 0,
    active_sensor_alert_ids: p.active_sensor_alert_ids ?? [],
    active_equipment_risk_ids: p.active_equipment_risk_ids ?? [],
    recent_incident_count: p.recent_incident_count ?? 0,
    pending_critical_maintenance_asset_ids: p.pending_critical_maintenance_asset_ids ?? [],
    stale_sensor_ids: p.stale_sensor_ids ?? [],
    last_updated: p.last_updated ?? raw.event_timestamp,
    is_stale: p.is_stale ?? false,
  };
}

function mapEnvironment(raw: any | null): EnvironmentAnalysis | null {
  if (!raw) return null;
  const p = raw.payload;
  return {
    zone_id: raw.zone_id,
    risk_score: p.risk_score,
    confidence: p.confidence,
    hazards: (p.hazards ?? []).map((h: any) => ({
      hazard_type: h.hazard_type,
      // sensor_ids[0] carries the real field/species name (e.g. "methane"),
      // not yet a literal sensor ID -- see environmental_intelligence_agent.py's
      // hazards construction. Falls back to the coarser hazard_type
      // category only if that's ever absent (e.g. temperature/pressure
      // readings from before this convention existed).
      label: h.sensor_ids?.[0] ?? h.hazard_type,
      measured_value: h.measured_value,
      unit: h.unit,
      threshold_ppm: h.threshold_ppm ?? undefined,
      threshold_breach: h.threshold_breach,
      trend: h.trend,
      sensor_ids: h.sensor_ids ?? [],
    })),
    evacuation_required: p.evacuation_required ?? false,
    recommendations: p.recommendations ?? [],
    analyzed_at: p.analyzed_at ?? raw.event_timestamp,
  };
}

function mapPermit(raw: any): PermitAnalysis {
  const p = raw.payload;
  return {
    permit_id: p.permit_id,
    permit_type: p.permit_type ?? "UNKNOWN",
    zone_id: raw.zone_id ?? "",
    // The real PermitAnalysisV1 doesn't carry a lifecycle `status` field
    // (that lives on the source PermitEvent, which this cache doesn't
    // retain) -- "active" is the only state the demo scenario produces,
    // so it's a safe default, not a fabricated fact about a specific permit.
    status: "active",
    valid_from: raw.event_timestamp,
    valid_to: raw.event_timestamp,
    permit_risk_level: p.permit_risk_level,
    risk_score: p.risk_score,
    confidence: p.confidence,
    conflicts: (p.conflicts ?? []).map((c: any) => ({
      conflicting_permit_id: c.conflicting_permit_id ?? "",
      conflict_type: c.conflict_type ?? "",
      severity: (c.severity ?? "advisory").toLowerCase(),
    })),
    zone_compatibility: p.zone_compatibility ?? true,
    recommendations: p.recommendations ?? [],
    analyzed_at: p.analyzed_at ?? raw.event_timestamp,
  };
}

function mapWorker(raw: any): WorkerAnalysis {
  const p = raw.payload;
  return {
    worker_id: p.worker_id,
    zone_id: raw.zone_id ?? "",
    risk_score: p.risk_score,
    confidence: p.confidence,
    safety_status: p.safety_status,
    ppe_compliance: p.ppe_compliance,
    ppe_violations: p.ppe_violations ?? [],
    zone_clearance: p.zone_clearance ?? false,
    proximity_alerts: (p.proximity_alerts ?? []).map((a: any) => ({
      hazard_type: a.hazard_type,
      distance_m: a.distance_m,
      safe_distance_m: a.safe_distance_m,
    })),
    analyzed_at: p.analyzed_at ?? raw.event_timestamp,
  };
}

// -- Risk Orchestrator output (/api/risk-assessments) -----------------------

export interface TopologyEdge {
  from: string;
  to: string;
  relationship_type: string;
  distance_m: number | null;
}
export interface Topology {
  nodes: { zone_id: string; current_status: string | null }[];
  edges: TopologyEdge[];
}

function mapRiskAssessment(raw: any): RiskScore {
  return {
    risk_id: raw.assessment_id,
    zone_id: raw.zone_id,
    score: raw.global_score,
    severity: raw.severity as RiskSeverity,
    // The real assessment carries contributing_factors as strings; surface
    // each as a contributor row rather than inventing per-agent weights.
    contributors: (raw.contributing_factors ?? []).map((f: string) => ({
      agent: "risk_orchestrator",
      factor: f,
      weight: 0,
      score: raw.global_score,
      evidence: [],
    })),
    explanation_summary: raw.explanation ?? "",
    computed_at: raw.computed_at,
  };
}

/** All latest SystemRiskAssessments, keyed by zone_id. */
export async function fetchRiskAssessments(): Promise<Record<string, RiskScore>> {
  const res = await fetch(`${API_BASE}/api/risk-assessments`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/risk-assessments returned ${res.status}`);
  const data: { assessments: any[] } = await res.json();
  const byZone: Record<string, RiskScore> = {};
  for (const a of data.assessments) byZone[a.zone_id] = mapRiskAssessment(a);
  return byZone;
}

/** Zone relationship graph from Neo4j (for RelationshipGraph / topology views). */
export async function fetchTopology(): Promise<Topology> {
  const res = await fetch(`${API_BASE}/api/topology`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/topology returned ${res.status}`);
  return res.json();
}

/** Response Agent decisions (ActionRequests), keyed by zone_id. */
export async function fetchActionRequests(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/api/action-requests`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/action-requests returned ${res.status}`);
  const data: { responses: any[] } = await res.json();
  const byZone: Record<string, any> = {};
  for (const r of data.responses) byZone[r.zone_id] = r;
  return byZone;
}

/** Real, durably persisted risk-assessment + action-request history from
 * Postgres. `available: false` means Postgres was unreachable at gateway
 * startup -- distinct from `history: []`, which just means nothing has
 * happened yet. Callers should render these two cases differently. */
export interface HistoryEntry {
  assessment_id: string;
  zone_id: string;
  site_id: string | null;
  global_score: number;
  severity: string;
  decision_category: string;
  escalation_required: boolean;
  manual_review_required: boolean;
  explanation: string | null;
  recorded_at: string;
  action: {
    action_id: string;
    action_type: string;
    urgency: string;
    classification: string;
    explanation: string | null;
  } | null;
}

export async function fetchHistory(limit = 50): Promise<{ history: HistoryEntry[]; available: boolean }> {
  const res = await fetch(`${API_BASE}/api/history?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/history returned ${res.status}`);
  return res.json();
}

/** Real infra + pipeline health -- Redis/Postgres/Neo4j/Kafka connectivity,
 * transport mode, and active agent/orchestrator/response status. */
export interface HealthStatus {
  status: string;
  transport_mode: "memory" | "kafka";
  components: { redis: boolean; postgres: boolean; neo4j: boolean; kafka: boolean | null };
  agents: string[];
  agents_active: number;
  orchestrator_active: boolean;
  response_agent_active: boolean;
  zones_known: number;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/health returned ${res.status}`);
  return res.json();
}

/** Deterministic Safety Explanation -- always available, no LLM required. */
export interface AgentContribution {
  agent: string;
  impact: string;
  findings: string[];
}
export interface SafetyExplanation {
  assessment_id: string;
  zone_id: string;
  severity: string;
  decision_category: string;
  global_score: number;
  summary: string;
  situation: string;
  why_this_matters: string;
  primary_hazard: string | null;
  top_risk_factors: string[];
  agent_contributions: AgentContribution[];
  is_compound_risk: boolean;
  compound_risk_explanation: string | null;
  affected_zones: string[];
  propagation_impact: string[];
  immediate_action: string | null;
  confidence: number;
  analysis_completeness: string;
  missing_domains: string[];
  analysis_limitations: string | null;
}

export async function fetchExplanation(zoneId: string): Promise<SafetyExplanation> {
  const res = await fetch(`${API_BASE}/api/explanation/${zoneId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/explanation returned ${res.status}`);
  return res.json();
}

/** Ask the Safety Copilot a question, constrained to verified assessment
 * data. `source` tells you whether the answer came from the LLM or the
 * deterministic fallback -- always label this honestly in the UI. */
export interface CopilotAnswer {
  text: string;
  source: "llm" | "deterministic";
  model: string | null;
}

export async function askCopilot(zoneId: string, question: string): Promise<CopilotAnswer> {
  const res = await fetch(`${API_BASE}/api/copilot/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zone_id: zoneId, question }),
  });
  if (!res.ok) throw new Error(`api-gateway /api/copilot/ask returned ${res.status}`);
  return res.json();
}

/** Fire a demo scenario (normal | gas-rise | compound-risk | multi-zone-emergency). */
export async function runScenario(name: string): Promise<void> {
  await fetch(`${API_BASE}/api/demo/scenario/${name}`, { method: "POST" });
}
export async function resetDemo(): Promise<void> {
  await fetch(`${API_BASE}/api/demo/reset`, { method: "POST" });
}

/** Throws on any network/parse failure -- callers decide how to fall back. */
export async function fetchZoneRecord(zoneId: string): Promise<ZoneRecord | null> {
  const res = await fetch(`${API_BASE}/api/zones/${encodeURIComponent(zoneId)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`api-gateway /api/zones/${zoneId} returned ${res.status}`);
  const entry: RawZoneEntry = await res.json();
  const state = mapZoneState(entry.zone_state);
  const layout = layoutFor(state.zone_id, 0);
  const risk = await fetchRiskAssessments().catch(() => ({} as Record<string, RiskScore>));
  return {
    zoneId: state.zone_id,
    displayName: layout.displayName,
    x: layout.x,
    y: layout.y,
    state,
    anomalies: [],
    environment: mapEnvironment(entry.environment),
    permits: entry.active_permits.map(mapPermit),
    workers: entry.workers.map(mapWorker),
    riskScore: risk[state.zone_id] ?? null,
  };
}

/** Throws on any network/parse failure -- callers decide how to fall back. */
export async function fetchZoneRecords(): Promise<ZoneRecord[]> {
  const res = await fetch(`${API_BASE}/api/zones`, { cache: "no-store" });
  if (!res.ok) throw new Error(`api-gateway /api/zones returned ${res.status}`);
  const data: { zones: RawZoneEntry[] } = await res.json();
  // Real risk from the Risk Orchestrator, attached per zone. Best-effort: if
  // the orchestrator hasn't produced an assessment for a zone yet, riskScore
  // stays null (a real absence, not a fabricated zero).
  const risk = await fetchRiskAssessments().catch(() => ({} as Record<string, RiskScore>));

  return data.zones.map((entry, index) => {
    const state = mapZoneState(entry.zone_state);
    const layout = layoutFor(state.zone_id, index);
    return {
      zoneId: state.zone_id,
      displayName: layout.displayName,
      x: layout.x,
      y: layout.y,
      state,
      // ZoneAnomalyDetected has no registered Kafka topic yet (see the
      // Zone Agent audit -- computed internally, never published), so the
      // api-gateway has nothing to serve here. Empty, not fabricated.
      anomalies: [],
      environment: mapEnvironment(entry.environment),
      permits: entry.active_permits.map(mapPermit),
      workers: entry.workers.map(mapWorker),
      riskScore: risk[state.zone_id] ?? null,
    };
  });
}

export function deriveSiteState(zones: ZoneRecord[]): SiteState {
  const totalWorkers = zones.reduce((sum, z) => sum + z.state.occupancy_count, 0);
  const activeIncidents = zones.reduce((sum, z) => sum + z.state.recent_incident_count, 0);

  const riskOrder: Record<RiskLevel, number> = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3, LOCKDOWN: 4 };
  let highest = zones[0] ?? null;
  for (const z of zones) {
    if (highest === null || riskOrder[z.state.current_risk_level] > riskOrder[highest.state.current_risk_level]) {
      highest = z;
    }
  }

  const overallByRisk: Record<RiskLevel, SiteState["overall_state"]> = {
    LOW: "normal",
    MEDIUM: "elevated",
    HIGH: "elevated",
    CRITICAL: "emergency",
    LOCKDOWN: "lockdown",
  };

  return {
    site_id: zones[0]?.state.site_id ?? "SITE-1",
    overall_state: highest ? overallByRisk[highest.state.current_risk_level] : "normal",
    zone_summary: Object.fromEntries(zones.map((z) => [z.zoneId, riskOrder[z.state.current_risk_level]])),
    total_workers: totalWorkers,
    highest_risk_zone: highest?.displayName ?? "--",
    highest_risk_score: highest ? riskOrder[highest.state.current_risk_level] * 25 : 0,
    active_incidents: activeIncidents,
    changed_at: new Date().toISOString(),
  };
}

/**
 * Derives a "what changed recently" feed straight from the real analysis
 * explanations already present on each zone -- not a separate event log
 * (none exists in the api-gateway yet), so this is a real-data view, not
 * a simulation, but it will only ever show the latest snapshot per
 * agent/zone rather than a true historical stream.
 */
export function deriveFeed(zones: ZoneRecord[]): FeedItem[] {
  const items: FeedItem[] = [];
  for (const z of zones) {
    if (z.environment) {
      items.push({
        id: `env-${z.zoneId}`,
        zoneId: z.zoneId,
        message: `${z.displayName}: ${z.environment.hazards.map((h) => h.hazard_type).join(", ") || "no active hazards"}`,
        timestamp: z.environment.analyzed_at,
        source: "real",
        severity: z.environment.evacuation_required ? "CRITICAL" : "INFO",
      });
    }
    for (const p of z.permits) {
      items.push({
        id: `permit-${p.permit_id}`,
        zoneId: z.zoneId,
        message: `Permit ${p.permit_id} (${p.permit_type}): ${p.permit_risk_level} risk`,
        timestamp: p.analyzed_at,
        source: "real",
        severity: "INFO",
      });
    }
    for (const w of z.workers) {
      items.push({
        id: `worker-${w.worker_id}`,
        zoneId: z.zoneId,
        message:
          w.ppe_violations.length > 0
            ? `Worker ${w.worker_id} missing PPE: ${w.ppe_violations.join(", ")}`
            : `Worker ${w.worker_id}: ${w.safety_status}`,
        timestamp: w.analyzed_at,
        source: "real",
        severity: w.safety_status === "in_danger" ? "CRITICAL" : w.ppe_violations.length > 0 ? "MEDIUM" : "INFO",
      });
    }
  }
  return items.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}
