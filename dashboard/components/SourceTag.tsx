import { DataSource } from "@/lib/contracts";

export default function SourceTag({ source }: { source: DataSource | "unavailable" }) {
  const config = {
    real: { label: "LIVE", bg: "var(--accent-soft)", fg: "var(--accent-strong)" },
    simulated: { label: "SIMULATED", bg: "var(--sim-soft)", fg: "var(--sim-color)" },
    unavailable: { label: "UNAVAILABLE", bg: "var(--surface-sunken)", fg: "var(--text-tertiary)" },
  }[source];

  return (
    <span
      title={
        source === "real"
          ? "Backed by live zone_intelligence_agent data"
          : source === "simulated"
          ? "Demo data shaped from the documented contract — no live agent produces this yet"
          : "No backend source exists for this yet"
      }
      style={{
        display: "inline-block",
        padding: "2px 7px",
        borderRadius: 5,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.06em",
        background: config.bg,
        color: config.fg,
        fontFamily: "var(--font-mono)",
      }}
    >
      {config.label}
    </span>
  );
}
