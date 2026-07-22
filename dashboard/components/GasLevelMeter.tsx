/**
 * GasLevelMeter.tsx
 *
 * One vertical, color-banded gauge per gas/environmental reading -- shows
 * BOTH the number (percentage of the real configured "critical" threshold
 * for that specific field) and a filled bar, so a viewer can see which gas
 * and how much at a glance, per the reference gauge image supplied.
 *
 * The percentage is computed from real backend data:
 *   percentage = measured_value / threshold_ppm * 100
 * where threshold_ppm is the real "critical" rung from
 * agents/environmental-intelligence-agent/engine/threshold_service.py's
 * ThresholdService.get_threshold(field_name, "critical") -- NOT a
 * frontend-invented number. See environmental_intelligence_agent.py's
 * hazards construction for where that value comes from.
 *
 * Bands (bottom to top, matching this dashboard's existing risk palette
 * from globals.css rather than inventing new colors):
 *   0-40%   var(--risk-normal)    (green)
 *   40-70%  var(--risk-warning)   (amber)
 *   70-88%  var(--risk-critical)  (red)
 *   88-100% var(--risk-emergency) (dark red)
 * The bar always shows the full band scale; a mask reveals only the
 * portion up to the current percentage, so the TOP of the filled color
 * directly encodes how close this reading is to its real critical
 * threshold.
 *
 * KNOWN CAVEAT, not hidden: ThresholdService derives ALL of its
 * thresholds (gas species and temperature/humidity/pressure alike) from a
 * single "higher is worse" assumption (advisory/warning/high/critical as
 * 0.5x/1x/2x/5x of one configured value). That's correct for methane, CO,
 * H2S, temperature, etc., but is NOT correct for oxygen, where LOWER
 * values are dangerous (deficiency) -- the "critical" threshold for
 * oxygen from this same service is a nonsensical 5x-of-normal upper bound,
 * not a real deficiency floor. This component will render a percentage
 * for oxygen using that same (wrong-direction) reference until
 * ThresholdService itself is fixed to branch on gas type -- flagged here
 * rather than silently producing a misleading oxygen gauge without
 * comment.
 */
const BANDS = [
  { upTo: 40, color: "var(--risk-normal)" },
  { upTo: 70, color: "var(--risk-warning)" },
  { upTo: 88, color: "var(--risk-critical)" },
  { upTo: 100, color: "var(--risk-emergency)" },
];

function bandGradient(): string {
  const stops: string[] = [];
  let prev = 0;
  for (const band of BANDS) {
    stops.push(`${band.color} ${prev}%`, `${band.color} ${band.upTo}%`);
    prev = band.upTo;
  }
  // gradient direction is bottom-to-top (0% band at the bottom)
  return `linear-gradient(to top, ${stops.join(", ")})`;
}

export default function GasLevelMeter({
  label,
  percentage,
  measuredValue,
  unit,
  breach,
  height = 130,
}: {
  label: string;
  /** null when no real threshold exists for this field -- rendered as "--", never fabricated */
  percentage: number | null;
  measuredValue: number;
  unit: string;
  breach: boolean;
  height?: number;
}) {
  const clamped = percentage === null ? 0 : Math.max(0, Math.min(100, percentage));
  const exceeds = percentage !== null && percentage > 100;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, width: 64 }}>
      <div
        className="mono"
        style={{
          fontWeight: 700,
          fontSize: 15,
          color: exceeds ? "var(--risk-emergency)" : breach ? "var(--risk-critical)" : "var(--text-primary)",
        }}
        title={percentage === null ? "No configured threshold for this field" : `${percentage.toFixed(1)}% of critical threshold`}
      >
        {percentage === null ? "--" : `${Math.round(percentage)}%`}
      </div>

      <div
        style={{
          position: "relative",
          width: 26,
          height,
          borderRadius: 13,
          overflow: "hidden",
          border: exceeds ? "2px solid var(--risk-emergency)" : "1px solid var(--border)",
          background: "var(--surface-sunken)",
          boxShadow: "var(--shadow-sm)",
          flexShrink: 0,
        }}
      >
        <div style={{ position: "absolute", inset: 0, background: bandGradient() }} />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: `${100 - clamped}%`,
            background: "var(--surface-sunken)",
            transition: "height 0.4s ease",
          }}
        />
        {exceeds && (
          <div
            style={{
              position: "absolute",
              top: 2,
              left: 0,
              right: 0,
              textAlign: "center",
              fontSize: 9,
              fontWeight: 700,
              color: "#fff",
              textShadow: "0 1px 2px rgba(0,0,0,0.4)",
            }}
          >
            !
          </div>
        )}
      </div>

      <div style={{ textAlign: "center" }}>
        <div style={{ fontWeight: 600, fontSize: 12, color: "var(--text-primary)" }}>{label}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
          {measuredValue}
          {unit}
        </div>
      </div>
    </div>
  );
}
