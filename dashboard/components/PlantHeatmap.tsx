"use client";

import Link from "next/link";
import { ZoneRecord } from "@/lib/contracts";
import { zoneStatus, statusColor, statusSoftColor } from "@/lib/viewModels";
import { Users, FileWarning } from "lucide-react";

export default function PlantHeatmap({ zones }: { zones: ZoneRecord[] }) {
  const cols = Math.max(...zones.map((z) => z.x)) + 1;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: 14,
      }}
    >
      {zones.map((zone) => {
        const status = zoneStatus(zone.state.current_risk_level);
        const hasHazard = zone.anomalies.length > 0;
        return (
          <Link
            key={zone.zoneId}
            href={`/zones/${zone.zoneId}`}
            style={{
              gridColumn: zone.x + 1,
              gridRow: zone.y + 1,
              display: "block",
              padding: "18px 18px 16px",
              borderRadius: "var(--radius-md)",
              border: `1px solid ${status === "NORMAL" ? "var(--border)" : statusColor[status]}22`,
              background: statusSoftColor[status],
              minHeight: 108,
              transition: "transform 120ms ease",
            }}
            className="zoneTile"
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)", fontWeight: 600, letterSpacing: "0.04em" }}>
                  {zone.zoneId.replace("ZONE-", "ZONE ")}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 1 }}>
                  {zone.displayName.split(" — ")[1]}
                </div>
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: statusColor[status],
                  letterSpacing: "0.04em",
                }}
              >
                {status}
              </span>
            </div>
            <div style={{ display: "flex", gap: 14, marginTop: 16, fontSize: 12, color: "var(--text-secondary)" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <Users size={13} /> {zone.state.occupancy_count}
              </span>
              {hasHazard && (
                <span style={{ display: "flex", alignItems: "center", gap: 4, color: statusColor[status], fontWeight: 600 }}>
                  <FileWarning size={13} /> {zone.anomalies.length} active
                </span>
              )}
            </div>
          </Link>
        );
      })}
      <style>{`.zoneTile:hover { transform: translateY(-2px); }`}</style>
    </div>
  );
}
