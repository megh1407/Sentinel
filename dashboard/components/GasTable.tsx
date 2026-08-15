import { EnvironmentAnalysis } from "@/lib/contracts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import SourceTag from "./SourceTag";
import GasLevelMeter from "./GasLevelMeter";

const trendIcon = { rising: TrendingUp, falling: TrendingDown, stable: Minus };

export default function GasTable({ data }: { data: EnvironmentAnalysis | null }) {
  if (!data) {
    return (
      <div style={{ padding: 20, color: "var(--text-tertiary)", fontSize: 13 }}>
        No environmental readings available for this zone. <SourceTag source="unavailable" />
      </div>
    );
  }

  return (
    <div>
      {/*
        Per-gas visual gauges -- percentage is measured_value / threshold_ppm
        (the real "critical" rung from ThresholdService, see
        environmental_intelligence_agent.py's hazards construction), not a
        frontend-invented number. threshold_ppm is only populated when a
        real threshold exists for that field (every gas species plus
        temperature/humidity/pressure today) -- shown as "--" otherwise,
        never fabricated.
      */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 20, paddingBottom: 4 }}>
        {data.hazards.map((h, idx) => (
          <GasLevelMeter
            key={`${h.label}-${idx}`}
            label={h.label}
            percentage={h.threshold_ppm ? (h.measured_value / h.threshold_ppm) * 100 : null}
            measuredValue={h.measured_value}
            unit={h.unit}
            breach={h.threshold_breach}
          />
        ))}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--text-tertiary)", fontSize: 11.5, letterSpacing: "0.04em" }}>
            <th style={{ padding: "0 8px 10px 0", fontWeight: 600 }}>GAS</th>
            <th style={{ padding: "0 8px 10px", fontWeight: 600 }}>READING</th>
            <th style={{ padding: "0 8px 10px", fontWeight: 600 }}>TREND</th>
            <th style={{ padding: "0 0 10px", fontWeight: 600 }}>STATUS</th>
          </tr>
        </thead>
        <tbody>
          {data.hazards.map((h, idx) => {
            const Icon = trendIcon[h.trend];
            return (
              <tr key={`${h.label}-${idx}`} style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ padding: "10px 8px 10px 0", fontWeight: 600 }}>{h.label}</td>
                <td style={{ padding: "10px 8px" }} className="mono">
                  {h.measured_value} {h.unit}
                </td>
                <td style={{ padding: "10px 8px", color: "var(--text-secondary)" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <Icon size={13} /> {h.trend}
                  </span>
                </td>
                <td style={{ padding: "10px 0" }}>
                  <span
                    style={{
                      fontWeight: 600,
                      color: h.threshold_breach ? "var(--risk-critical)" : "var(--risk-normal)",
                    }}
                  >
                    {h.threshold_breach ? "High" : "Normal"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
