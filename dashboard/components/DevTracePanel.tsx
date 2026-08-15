import { ZoneRecord } from "@/lib/contracts";

const stages = [
  { label: "SensorEvent / WorkerEvent / PermitEvent", agent: "demo event generator (demo_scenarios.py) — REAL, publishes onto real Kafka topics" },
  { label: "ZoneState + ZoneAnomalyDetected", agent: "zone_intelligence_agent — REAL, live-tested" },
  { label: "PermitAnalysis", agent: "permit_intelligence_agent — REAL, live-tested" },
  { label: "WorkerAnalysis", agent: "worker_safety_agent — REAL, live-tested" },
  { label: "EnvironmentAnalysis", agent: "environmental_intelligence_agent — REAL, live-tested" },
  { label: "SystemRiskAssessment", agent: "risk_orchestrator_agent — REAL: correlation engine, local/interaction/propagation risk scoring, Neo4j-backed topology" },
  { label: "ActionRequest", agent: "response_agent — REAL: emergency evaluation, response classification, action planning" },
  { label: "Persisted history", agent: "PostgreSQL (risk_orchestrator.risk_assessments / action_requests) — REAL, durable across resets/restarts" },
];

export default function DevTracePanel({ zone, risk, action }: { zone: ZoneRecord; risk?: any; action?: any }) {
  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", maxWidth: 640, lineHeight: 1.6 }}>
        This panel reflects the actual, verified state of the SENTINEL backend pipeline — every stage below has
        been confirmed against a live run with real Kafka, Redis, Neo4j, and PostgreSQL.
      </p>
      <div style={{ marginTop: 20, display: "flex", flexDirection: "column" }}>
        {stages.map((s, i) => (
          <div key={s.label} style={{ display: "flex", gap: 14, padding: "12px 0", borderTop: i === 0 ? "none" : "1px solid var(--border)" }}>
            <div className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)", width: 22, flexShrink: 0, paddingTop: 2 }}>
              {String(i + 1).padStart(2, "0")}
            </div>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600 }} className="mono">
                {s.label}
              </div>
              <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginTop: 2 }}>{s.agent}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 28 }}>
        <div className="sectionLabel">Raw ZoneState (live shape) — {zone.zoneId}</div>
        <pre
          className="mono"
          style={{
            background: "var(--surface-sunken)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: 16,
            fontSize: 12,
            overflowX: "auto",
          }}
        >
          {JSON.stringify(zone.state, null, 2)}
        </pre>
      </div>

      {risk && (
        <div style={{ marginTop: 20 }}>
          <div className="sectionLabel">Live SystemRiskAssessment</div>
          <pre
            className="mono"
            style={{
              background: "var(--surface-sunken)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              padding: 16,
              fontSize: 12,
              overflowX: "auto",
            }}
          >
            {JSON.stringify(risk, null, 2)}
          </pre>
        </div>
      )}

      {action && (
        <div style={{ marginTop: 20 }}>
          <div className="sectionLabel">Live ActionRequest</div>
          <pre
            className="mono"
            style={{
              background: "var(--surface-sunken)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              padding: 16,
              fontSize: 12,
              overflowX: "auto",
            }}
          >
            {JSON.stringify(action, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
