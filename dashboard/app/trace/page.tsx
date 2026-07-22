"use client";

import { useState } from "react";
import { zones } from "@/lib/mockData";
import DevTracePanel from "@/components/DevTracePanel";

export default function TracePage() {
  const [zoneId, setZoneId] = useState(zones[0].zoneId);
  const zone = zones.find((z) => z.zoneId === zoneId)!;

  return (
    <div>
      <div className="pageHeader">
        <h1>System Trace</h1>
        <p>Developer / debug view — event lineage and backend implementation status. Not the default operator experience.</p>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {zones.map((z) => (
          <button
            key={z.zoneId}
            onClick={() => setZoneId(z.zoneId)}
            style={{
              fontSize: 12.5,
              fontWeight: 600,
              padding: "6px 12px",
              borderRadius: 999,
              border: "1px solid var(--border)",
              background: z.zoneId === zoneId ? "var(--accent-soft)" : "var(--surface)",
              color: z.zoneId === zoneId ? "var(--accent-strong)" : "var(--text-secondary)",
            }}
          >
            {z.zoneId}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 24 }}>
        <DevTracePanel zone={zone} />
      </div>
    </div>
  );
}
