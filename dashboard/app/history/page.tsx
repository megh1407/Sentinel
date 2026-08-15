"use client";

import { useEffect, useState } from "react";
import { fetchHistory, HistoryEntry } from "@/lib/api";
import SourceTag from "@/components/SourceTag";

const SEVERITY_COLOR: Record<string, string> = {
  catastrophic: "var(--risk-emergency)",
  critical: "var(--risk-critical)",
  high: "var(--risk-critical)",
  moderate: "var(--risk-warning)",
  low: "var(--risk-watch)",
  negligible: "var(--risk-normal)",
  safe: "var(--risk-normal)",
};
function severityColor(s: string): string {
  return SEVERITY_COLOR[s] ?? "var(--text-secondary)";
}

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [available, setAvailable] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchHistory(100);
        if (cancelled) return;
        setHistory(data.history);
        setAvailable(data.available);
      } catch {
        if (!cancelled) setAvailable(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 6000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div>
      <div className="pageHeader">
        <h1>Safety Assessment History</h1>
        <p>Durable audit trail of every SystemRiskAssessment and the response it produced, persisted in PostgreSQL.</p>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <SourceTag source="real" />
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
          Risk Orchestrator + Response Agent, persisted via HistoryRepository
        </span>
      </div>

      {!available && (
        <div className="card" style={{ padding: 24, color: "var(--text-secondary)" }}>
          PostgreSQL is unreachable right now, so no history can be shown. This is a live infrastructure
          status, not fabricated data — check that the Postgres container is running and reachable.
        </div>
      )}

      {available && !loading && history.length === 0 && (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-secondary)" }}>
          No assessments recorded yet. Run a demo scenario to populate real history.
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {history.map((h) => (
          <div key={h.assessment_id} className="card" style={{ padding: "14px 20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
              <div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <span
                    className="mono"
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: severityColor(h.severity),
                      textTransform: "uppercase",
                      letterSpacing: "0.03em",
                    }}
                  >
                    {h.severity}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{h.zone_id}</span>
                  <span className="mono" style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                    score {h.global_score.toFixed(1)}
                  </span>
                </div>
                {h.action && (
                  <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginTop: 6, maxWidth: 640 }}>
                    {h.action.explanation}
                  </div>
                )}
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                  {new Date(h.recorded_at + "Z").toLocaleString()}
                </div>
                {h.action && (
                  <div
                    className="mono"
                    style={{ fontSize: 11, fontWeight: 600, marginTop: 4, color: "var(--text-secondary)" }}
                  >
                    {h.action.action_type.replace(/_/g, " ")}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
