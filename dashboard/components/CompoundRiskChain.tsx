import { RiskContributor } from "@/lib/contracts";
import { Plus } from "lucide-react";

/**
 * This is the core value proposition of SENTINEL (brief Section 8):
 * showing that individually moderate signals become dangerous together.
 * Built from ExplanationObject.risk_contributors — real data when the
 * anomaly came from zone_intelligence_agent, simulated when it came from
 * the demo RiskScore.
 */
export default function CompoundRiskChain({
  contributors,
  summary,
}: {
  contributors: RiskContributor[];
  summary: string;
}) {
  if (contributors.length === 0) return null;

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        padding: 24,
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 10,
          justifyContent: "center",
        }}
      >
        {contributors.map((c, i) => (
          <div key={c.factor_name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--radius-sm)",
                padding: "10px 14px",
                background: "var(--surface-sunken)",
                minWidth: 150,
              }}
            >
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>{c.description}</div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 3, fontFamily: "var(--font-mono)" }}>
                {c.factor_name} · +{c.contribution_score}
              </div>
            </div>
            {i < contributors.length - 1 && <Plus size={16} color="var(--text-tertiary)" />}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "center", margin: "18px 0" }}>
        <svg width="2" height="28" aria-hidden>
          <line x1="1" y1="0" x2="1" y2="28" stroke="var(--border-strong)" strokeWidth="2" strokeDasharray="1 5" />
        </svg>
      </div>

      <div style={{ display: "flex", justifyContent: "center" }}>
        <div
          style={{
            background: "var(--risk-critical-soft)",
            color: "var(--risk-critical)",
            border: "1px solid var(--risk-critical)33",
            borderRadius: "var(--radius-sm)",
            padding: "12px 22px",
            fontWeight: 700,
            fontSize: 14,
            letterSpacing: "0.02em",
          }}
        >
          COMPOUND RISK
        </div>
      </div>

      <p
        style={{
          textAlign: "center",
          maxWidth: 560,
          margin: "16px auto 0",
          color: "var(--text-secondary)",
          fontSize: 13.5,
          lineHeight: 1.6,
        }}
      >
        {summary}
      </p>
    </div>
  );
}
