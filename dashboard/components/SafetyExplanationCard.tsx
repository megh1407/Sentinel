"use client";

import { useEffect, useState } from "react";
import { fetchExplanation, SafetyExplanation } from "@/lib/api";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

const SEVERITY_COLOR: Record<string, string> = {
  catastrophic: "var(--risk-emergency)",
  critical: "var(--risk-critical)",
  high: "var(--risk-critical)",
  moderate: "var(--risk-warning)",
  low: "var(--risk-watch)",
  negligible: "var(--risk-normal)",
  safe: "var(--risk-normal)",
};

const IMPACT_COLOR: Record<string, string> = {
  CRITICAL: "var(--risk-emergency)",
  HIGH: "var(--risk-critical)",
  MODERATE: "var(--risk-warning)",
  LOW: "var(--risk-watch)",
};

export default function SafetyExplanationCard({ zoneId }: { zoneId: string }) {
  const [explanation, setExplanation] = useState<SafetyExplanation | null>(null);
  const [showTechnical, setShowTechnical] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const exp = await fetchExplanation(zoneId);
        if (!cancelled) {
          setExplanation(exp);
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [zoneId]);

  if (error || !explanation) return null; // no assessment yet for this zone -- nothing to explain

  const color = SEVERITY_COLOR[explanation.severity] ?? "var(--text-secondary)";

  return (
    <div className="card" style={{ padding: 24, marginBottom: 24 }}>
      {/* Quick summary -- understand the situation in a few seconds */}
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 16 }}>
        <AlertTriangle size={20} color={color} style={{ marginTop: 2, flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{explanation.summary}</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{explanation.situation}</div>
        </div>
      </div>

      {/* Why this matters */}
      <p style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--text-secondary)", marginBottom: 18 }}>
        {explanation.why_this_matters}
      </p>

      {/* Compound risk visualization */}
      {explanation.is_compound_risk && (
        <div style={{ marginBottom: 18 }}>
          <div className="sectionLabel">Compound risk</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            {explanation.agent_contributions
              .filter((c) => !c.agent.includes("topology"))
              .map((c, i, arr) => (
                <div key={c.agent} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div
                    style={{
                      border: `1px solid ${IMPACT_COLOR[c.impact] ?? "var(--border)"}55`,
                      borderRadius: "var(--radius-sm)",
                      padding: "8px 12px",
                      background: "var(--surface-sunken)",
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 700 }}>{c.agent}</div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>{c.findings[0]}</div>
                  </div>
                  {i < arr.length - 1 && <span style={{ color: "var(--text-tertiary)", fontWeight: 700 }}>+</span>}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Agent contribution view */}
      <div style={{ marginBottom: 18 }}>
        <div className="sectionLabel">Safety intelligence contributors</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {explanation.agent_contributions.map((c) => (
            <div key={c.agent} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <span
                className="mono"
                style={{
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: IMPACT_COLOR[c.impact] ?? "var(--text-secondary)",
                  minWidth: 68,
                  paddingTop: 2,
                }}
              >
                {c.impact}
              </span>
              <div style={{ fontSize: 12.5 }}>
                <span style={{ fontWeight: 600 }}>{c.agent}</span>
                <span style={{ color: "var(--text-secondary)" }}> — {c.findings.join("; ")}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Propagation explanation */}
      {explanation.propagation_impact.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <div className="sectionLabel">Cross-zone propagation</div>
          {explanation.propagation_impact.map((p, i) => (
            <p key={i} style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "4px 0" }}>
              {p}
            </p>
          ))}
        </div>
      )}

      {/* Immediate action */}
      {explanation.immediate_action && (
        <div style={{ marginBottom: 18 }}>
          <div className="sectionLabel">Recommended action</div>
          <div
            style={{
              background: "var(--risk-emergency-soft)",
              color: "var(--risk-emergency)",
              fontWeight: 600,
              fontSize: 13,
              padding: "10px 14px",
              borderRadius: "var(--radius-sm)",
            }}
          >
            {explanation.immediate_action}
          </div>
        </div>
      )}

      {/* Missing data disclosure -- never hidden */}
      {explanation.analysis_limitations && (
        <p style={{ fontSize: 11.5, color: "var(--text-tertiary)", marginBottom: 18 }}>
          {explanation.analysis_limitations}
        </p>
      )}

      {/* Technical breakdown -- available, not primary */}
      <button
        onClick={() => setShowTechnical((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          fontWeight: 600,
          color: "var(--text-tertiary)",
          background: "none",
          border: "none",
          padding: 0,
        }}
      >
        {showTechnical ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Technical details
      </button>
      {showTechnical && (
        <div style={{ marginTop: 10, fontSize: 12 }} className="mono">
          <div>Global score: {explanation.global_score.toFixed(2)}</div>
          <div>Confidence: {(explanation.confidence * 100).toFixed(1)}%</div>
          <div>Analysis completeness: {explanation.analysis_completeness}</div>
          <div>Top factors: {explanation.top_risk_factors.length}</div>
        </div>
      )}
    </div>
  );
}
