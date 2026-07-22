"use client";

import { useState } from "react";
import { zones } from "@/lib/mockData";
import { zoneStatus, statusColor } from "@/lib/viewModels";
import EmergencyOverlay from "@/components/EmergencyOverlay";
import Link from "next/link";
import { Siren } from "lucide-react";

export default function EmergencyPage() {
  const critical = zones.filter((z) => zoneStatus(z.state.current_risk_level) === "CRITICAL");
  const [openZone, setOpenZone] = useState<string | null>(null);

  return (
    <div>
      <div className="pageHeader">
        <h1>Emergency Center</h1>
        <p>Active critical events requiring acknowledgement or response.</p>
      </div>

      {critical.length === 0 && (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-secondary)" }}>
          No active emergencies. All zones within acceptable risk levels.
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {critical.map((zone) => {
          const top = zone.anomalies[0];
          return (
            <div
              key={zone.zoneId}
              className="card"
              style={{
                padding: 20,
                borderColor: "var(--risk-critical)33",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                <Siren size={20} color="var(--risk-critical)" style={{ marginTop: 2 }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14.5 }}>{zone.displayName}</div>
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 3, maxWidth: 520 }}>
                    {top?.explanation.summary}
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={() => setOpenZone(zone.zoneId)}
                  style={{
                    background: "var(--risk-critical)",
                    color: "#fff",
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    padding: "8px 16px",
                    fontWeight: 600,
                    fontSize: 13,
                  }}
                >
                  Open response
                </button>
                <Link
                  href={`/zones/${zone.zoneId}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--accent)",
                  }}
                >
                  Zone details
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {openZone &&
        (() => {
          const z = zones.find((z) => z.zoneId === openZone);
          return z ? <EmergencyOverlay key={z.zoneId} zone={z} /> : null;
        })()}
    </div>
  );
}
