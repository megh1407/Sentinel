import { ZoneRecord } from "@/lib/contracts";
import { zoneStatus, activeAnomaly } from "@/lib/viewModels";
import StatusPill from "./StatusPill";
import SourceTag from "./SourceTag";

export default function SituationSummary({ zone }: { zone: ZoneRecord }) {
  const status = zoneStatus(zone.state.current_risk_level);
  const top = activeAnomaly(zone);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
          {zone.displayName} is currently
        </h2>
        <StatusPill status={status} pulse />
      </div>

      {top ? (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--text-primary)", margin: 0, maxWidth: 620 }}>
            {top.explanation.summary}
          </p>
          <SourceTag source="real" />
        </div>
      ) : (
        <p style={{ fontSize: 14, color: "var(--text-secondary)", margin: 0 }}>
          No active anomalies. Conditions are within normal operating range.
        </p>
      )}
    </div>
  );
}
