import { ZoneRecord } from "@/lib/contracts";
import SourceTag from "./SourceTag";

export default function RelationshipGraph({ zone }: { zone: ZoneRecord }) {
  const worker = zone.workers[0];
  const permit = zone.permits[0];
  const anomaly = zone.anomalies[0];

  const nodes: { label: string; sub?: string }[] = [{ label: zone.zoneId }];
  if (worker) nodes.push({ label: worker.worker_id, sub: worker.ppe_violations[0] ?? "PPE ok" });
  if (permit) nodes.push({ label: permit.permit_type, sub: permit.status });
  if (zone.state.active_sensor_alert_ids[0]) nodes.push({ label: zone.state.active_sensor_alert_ids[0], sub: "sensor" });
  if (anomaly) nodes.push({ label: anomaly.anomaly_type.replace(/_/g, " "), sub: anomaly.severity });

  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 className="sectionLabel" style={{ margin: 0 }}>
          What&apos;s connected to this risk
        </h3>
        <SourceTag source="simulated" />
      </div>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 0 }}>
        {nodes.map((n, i) => (
          <div key={n.label} style={{ display: "flex", alignItems: "center" }}>
            <div
              style={{
                border: "1px solid var(--border-strong)",
                borderRadius: 999,
                padding: "8px 16px",
                background: i === 0 ? "var(--accent-soft)" : "var(--surface-sunken)",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 12.5, fontWeight: 600, textTransform: i === 0 ? "none" : "capitalize" }}>
                {n.label}
              </div>
              {n.sub && <div style={{ fontSize: 10.5, color: "var(--text-tertiary)" }}>{n.sub}</div>}
            </div>
            {i < nodes.length - 1 && (
              <svg width="34" height="2" style={{ margin: "0 4px" }} aria-hidden>
                <line x1="0" y1="1" x2="34" y2="1" stroke="var(--border-strong)" strokeWidth="2" />
              </svg>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
