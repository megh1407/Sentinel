import { ZoneRecord } from "@/lib/contracts";
import SourceTag from "./SourceTag";
import GasTable from "./GasTable";
import PermitCard from "./PermitCard";
import PPECard from "./PPECard";

function Panel({
  title,
  source,
  children,
}: {
  title: string;
  source: "real" | "simulated";
  children: React.ReactNode;
}) {
  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h3 className="sectionLabel" style={{ margin: 0 }}>
          {title}
        </h3>
        <SourceTag source={source} />
      </div>
      {children}
    </div>
  );
}

export default function ContributingSignals({ zone, live }: { zone: ZoneRecord; live: boolean }) {
  const source = live ? "real" : "simulated";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <Panel title="Environment" source={source}>
        <GasTable data={zone.environment} />
      </Panel>

      <Panel title="Permits" source={source}>
        {zone.permits.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {zone.permits.map((p) => (
              <PermitCard key={p.permit_id} permit={p} />
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--text-tertiary)", fontSize: 13 }}>No permits currently active.</div>
        )}
      </Panel>

      <Panel title="Workers &amp; PPE" source={source}>
        {zone.workers.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {zone.workers.map((w) => (
              <PPECard key={w.worker_id} worker={w} />
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {zone.state.occupancy_count} workers present, no PPE detail available for this zone.
          </div>
        )}
      </Panel>

      <Panel title="Zone Conditions" source="real">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 16px", fontSize: 13.5 }}>
          <Metric label="Occupancy" value={zone.state.occupancy_count} />
          <Metric label="Active anomalies" value={zone.anomalies.length} />
          <Metric label="Sensor alerts" value={zone.state.active_sensor_alert_ids.length} />
          <Metric label="Recent incidents" value={zone.state.recent_incident_count} />
          <Metric label="Equipment risks" value={zone.state.active_equipment_risk_ids.length} />
          <Metric label="Stale sensors" value={zone.state.stale_sensor_ids.length} />
        </div>
      </Panel>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div style={{ color: "var(--text-tertiary)", fontSize: 11.5 }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: 17 }} className="mono">
        {value}
      </div>
    </div>
  );
}
