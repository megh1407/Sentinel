"use client";

import { useEffect, useState } from "react";
import { fetchZoneRecords, fetchRiskAssessments, fetchActionRequests } from "@/lib/api";
import { ZoneRecord, RiskScore } from "@/lib/contracts";
import DevTracePanel from "@/components/DevTracePanel";

export default function TracePage() {
  const [zones, setZones] = useState<ZoneRecord[]>([]);
  const [risks, setRisks] = useState<Record<string, RiskScore>>({});
  const [actions, setActions] = useState<Record<string, any>>({});
  const [zoneId, setZoneId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [z, r, a] = await Promise.all([fetchZoneRecords(), fetchRiskAssessments(), fetchActionRequests()]);
        if (cancelled) return;
        setZones(z);
        setRisks(r);
        setActions(a);
        if (!zoneId && z.length > 0) setZoneId(z[0].zoneId);
      } catch {
        // gateway unreachable -- leave lists empty rather than fabricating
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const zone = zones.find((z) => z.zoneId === zoneId);

  return (
    <div>
      <div className="pageHeader">
        <h1>System Trace</h1>
        <p>Live event lineage from the real backend pipeline — event, agent, risk assessment, response.</p>
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

      {zone ? (
        <div className="card" style={{ padding: 24 }}>
          <DevTracePanel zone={zone} risk={risks[zone.zoneId]} action={actions[zone.zoneId]} />
        </div>
      ) : (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-secondary)" }}>
          No zones reporting yet. Run a demo scenario to populate live trace data.
        </div>
      )}
    </div>
  );
}
