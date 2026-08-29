"use client";

import { useEffect, useState } from "react";
import { fetchZoneRecords, fetchActionRequests } from "@/lib/api";
import { RiskScore, ZoneRecord } from "@/lib/contracts";
import EmergencyOverlay, { EmergencyActionRequest } from "@/components/EmergencyOverlay";
import Link from "next/link";
import { Siren } from "lucide-react";

const CRITICAL_SEVERITIES = new Set(["catastrophic", "critical"]);

export default function EmergencyPage() {
  const [zones, setZones] = useState<ZoneRecord[]>([]);
  const [actions, setActions] = useState<Record<string, EmergencyActionRequest>>({});
  const [openZone, setOpenZone] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [zoneRecords, actionsByZone] = await Promise.all([fetchZoneRecords(), fetchActionRequests()]);
        if (cancelled) return;
        setZones(zoneRecords);
        setActions(actionsByZone);
      } catch {
        // gateway unreachable -- leave lists empty rather than fabricating
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const critical = zones.filter((z) => z.riskScore && CRITICAL_SEVERITIES.has(z.riskScore.severity));

  return (
    <div>
      <div className="pageHeader">
        <h1>Emergency Center</h1>
        <p>Active critical events requiring acknowledgement or response.</p>
      </div>

      {!loading && critical.length === 0 && (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-secondary)" }}>
          No active emergencies. All zones within acceptable risk levels.
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {critical.map((zone) => {
          const risk = zone.riskScore as RiskScore;
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
                    {actions[zone.zoneId]?.explanation ?? risk.explanation_summary}
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
          const zone = zones.find((z) => z.zoneId === openZone);
          if (!zone?.riskScore) return null;
          return (
            <EmergencyOverlay
              zoneId={zone.zoneId}
              risk={zone.riskScore}
              action={actions[zone.zoneId] ?? null}
              onDismiss={() => setOpenZone(null)}
            />
          );
        })()}
    </div>
  );
}
