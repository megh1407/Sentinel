"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RiskScore } from "@/lib/contracts";
import { fetchExplanation, SafetyExplanation } from "@/lib/api";
import { Siren, X } from "lucide-react";
import SourceTag from "./SourceTag";

export interface EmergencyActionRequest {
  emergency: boolean;
  classification: string;
  action_type: string;
  urgency: string;
  escalation_required: boolean;
  manual_review_required: boolean;
  affected_zones: string[];
  explanation: string;
}

export default function EmergencyOverlay({
  zoneId,
  risk,
  action,
  onDismiss,
}: {
  zoneId: string;
  risk: RiskScore;
  action: EmergencyActionRequest | null;
  onDismiss: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [explanation, setExplanation] = useState<SafetyExplanation | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchExplanation(zoneId)
      .then((exp) => {
        if (!cancelled) setExplanation(exp);
      })
      .catch(() => {
        // Explanation is a nice-to-have layer here -- the popup already
        // has real risk+action data without it, so fail silently.
      });
    return () => {
      cancelled = true;
    };
  }, [zoneId]);

  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(20, 14, 12, 0.42)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: 20,
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          borderRadius: "var(--radius-lg)",
          maxWidth: 560,
          width: "100%",
          boxShadow: "0 24px 64px rgba(20,10,8,0.35)",
          border: "1px solid var(--risk-emergency)33",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: "var(--risk-emergency)",
            color: "#fff",
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <Siren size={20} strokeWidth={2.2} />
          <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
            {risk.severity === "catastrophic" ? "CRITICAL COMPOUND RISK" : "SAFETY EMERGENCY"}
          </span>
          <button
            onClick={onDismiss}
            aria-label="Close (details remain available on the zone page)"
            style={{
              marginLeft: "auto",
              background: "transparent",
              border: "none",
              color: "#fff",
              opacity: 0.85,
              padding: 4,
            }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{ fontSize: 13, color: "var(--text-tertiary)", marginBottom: 4 }}>
            {zoneId} &middot; risk score {risk.score.toFixed(1)}
          </div>
          <p style={{ fontSize: 15, lineHeight: 1.6, margin: "0 0 18px" }}>
            {action?.explanation ?? risk.explanation_summary}
          </p>

          {explanation && (
            <div style={{ marginBottom: 18 }}>
              <div className="sectionLabel">Why this is an emergency</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {explanation.agent_contributions.map((c) => (
                  <span
                    key={c.agent}
                    className="mono"
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "4px 10px",
                      borderRadius: 999,
                      background: "var(--surface-sunken)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    {c.agent.replace(" Agent", "").replace(" (topology)", "")}
                  </span>
                ))}
                {explanation.propagation_impact.length > 0 && (
                  <span
                    className="mono"
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "4px 10px",
                      borderRadius: 999,
                      background: "var(--surface-sunken)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    Cross-zone propagation
                  </span>
                )}
              </div>
            </div>
          )}

          <div style={{ marginBottom: 18 }}>
            <div className="sectionLabel">Technical breakdown</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.8 }}>
              {risk.contributors.map((c, i) => (
                <li key={i}>{c.factor}</li>
              ))}
            </ul>
          </div>

          {action && (
            <div style={{ marginBottom: 18 }}>
              <div className="sectionLabel">Recommended action</div>
              <div
                style={{
                  background: "var(--risk-emergency-soft)",
                  color: "var(--risk-emergency)",
                  fontWeight: 700,
                  fontSize: 13.5,
                  padding: "10px 14px",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                {action.action_type.replace(/_/g, " ")} &middot; {action.urgency} URGENCY
                {action.affected_zones.length > 1 && (
                  <> &middot; affects {action.affected_zones.join(", ")}</>
                )}
              </div>
              <p style={{ fontSize: 11.5, color: "var(--text-tertiary)", marginTop: 8, lineHeight: 1.5 }}>
                SENTINEL recommends procedural response only. It is not a replacement for certified SIS/PSD systems
                and cannot actuate SCADA setpoints, valves, or ESD systems directly.
                {action.manual_review_required && " Manual review is required before this action proceeds."}
              </p>
            </div>
          )}

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button
              onClick={() => setAcknowledged(true)}
              disabled={acknowledged}
              style={{
                background: acknowledged ? "var(--surface-sunken)" : "var(--accent)",
                color: acknowledged ? "var(--text-secondary)" : "#fff",
                border: "none",
                borderRadius: "var(--radius-sm)",
                padding: "10px 18px",
                fontWeight: 600,
                fontSize: 13.5,
              }}
            >
              {acknowledged ? "Acknowledged" : "Acknowledge"}
            </button>
            <Link href={`/zones/${zoneId}`} onClick={onDismiss} style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)" }}>
              View full zone details &rarr;
            </Link>
            <span style={{ marginLeft: "auto" }}>
              <SourceTag source="real" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
