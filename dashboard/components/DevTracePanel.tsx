import { ZoneRecord } from "@/lib/contracts";

const stages = [
  { label: "SensorEvent / WorkerEvent / PermitEvent", agent: "ingestion-gateway (not implemented — no code beyond Dockerfile)" },
  { label: "ZoneState + ZoneAnomalyDetected", agent: "zone_intelligence_agent — REAL, live-tested" },
  { label: "PermitAnalysis", agent: "permit_intelligence_agent — not implemented" },
  { label: "WorkerAnalysis", agent: "worker_safety_agent — not implemented" },
  { label: "EnvironmentAnalysis", agent: "environmental_intelligence_agent — code exists, process() returns None (blocked on gas-species routing + missing schema)" },
  { label: "RiskScore", agent: "risk_orchestrator_agent — domain entities only, no concrete scoring engine wired" },
];

export default function DevTracePanel({ zone }: { zone: ZoneRecord }) {
  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", maxWidth: 640, lineHeight: 1.6 }}>
        This panel reflects the actual state of the SENTINEL backend as of this audit — not an idealized pipeline.
        Use it to see exactly which stage is real versus simulated before wiring a new screen to it.
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
    </div>
  );
}
