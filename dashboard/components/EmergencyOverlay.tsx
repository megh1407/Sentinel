"use client";

import { useState } from "react";
import Link from "next/link";
import { ZoneRecord } from "@/lib/contracts";
import { Siren, X } from "lucide-react";
import SourceTag from "./SourceTag";

export default function EmergencyOverlay({ zone }: { zone: ZoneRecord }) {
  const [dismissed, setDismissed] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const top = zone.anomalies[0];
  if (dismissed || !top) return null;

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
            CRITICAL COMPOUND RISK
          </span>
          <button
            onClick={() => setDismissed(true)}
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
          <div style={{ fontSize: 13, color: "var(--text-tertiary)", marginBottom: 4 }}>{zone.zoneId}</div>
          <p style={{ fontSize: 15, lineHeight: 1.6, margin: "0 0 18px" }}>{top.explanation.summary}</p>

          <div style={{ marginBottom: 18 }}>
            <div className="sectionLabel">Why</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.8 }}>
              {top.explanation.reasoning_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>

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
              IMMEDIATE EVACUATION / SAFETY RESPONSE
            </div>
            <p style={{ fontSize: 11.5, color: "var(--text-tertiary)", marginTop: 8, lineHeight: 1.5 }}>
              SENTINEL recommends procedural response only. It is not a replacement for certified SIS/PSD systems
              and cannot actuate SCADA setpoints, valves, or ESD systems directly.
            </p>
          </div>

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
            <Link
              href={`/zones/${zone.zoneId}`}
              onClick={() => setDismissed(true)}
              style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)" }}
            >
              View full zone details →
            </Link>
            <span style={{ marginLeft: "auto" }}>
              <SourceTag source="simulated" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
