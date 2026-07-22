import { notFound } from "next/navigation";
import Link from "next/link";
import { zones as mockZones, getZone as getMockZone } from "@/lib/mockData";
import { fetchZoneRecord, fetchZoneRecords } from "@/lib/api";
import { timeAgo } from "@/lib/viewModels";
import { ZoneRecord } from "@/lib/contracts";
import SituationSummary from "@/components/SituationSummary";
import ContributingSignals from "@/components/ContributingSignals";
import CompoundRiskChain from "@/components/CompoundRiskChain";
import RelationshipGraph from "@/components/RelationshipGraph";
import SourceTag from "@/components/SourceTag";

/**
 * Phase 10 wiring, same honest pattern as app/page.tsx: try the real
 * api-gateway first, fall back to lib/mockData.ts only if that fetch
 * fails or the zone genuinely isn't known to the gateway yet. The
 * SourceTag on screen reflects which one actually happened.
 */
async function loadZone(zoneId: string): Promise<{ zone: ZoneRecord | null; navZones: ZoneRecord[]; live: boolean }> {
  try {
    const [zone, navZones] = await Promise.all([fetchZoneRecord(zoneId), fetchZoneRecords()]);
    if (zone) {
      return { zone, navZones: navZones.length ? navZones : mockZones, live: true };
    }
    // Gateway reachable but doesn't know this zone yet -- fall back to
    // mock so a direct link doesn't 404 during a demo, but don't claim LIVE.
    return { zone: getMockZone(zoneId) ?? null, navZones: mockZones, live: false };
  } catch {
    return { zone: getMockZone(zoneId) ?? null, navZones: mockZones, live: false };
  }
}

export default async function ZoneDetailPage({ params }: { params: Promise<{ zoneId: string }> }) {
  const { zoneId } = await params;
  const { zone, navZones, live } = await loadZone(zoneId);
  if (!zone) return notFound();
  const top = zone.anomalies[0];

  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 18 }}>
        {navZones.map((z) => (
          <Link
            key={z.zoneId}
            href={`/zones/${z.zoneId}`}
            style={{
              fontSize: 12.5,
              fontWeight: 600,
              padding: "6px 12px",
              borderRadius: 999,
              background: z.zoneId === zone.zoneId ? "var(--accent-soft)" : "var(--surface-sunken)",
              color: z.zoneId === zone.zoneId ? "var(--accent-strong)" : "var(--text-secondary)",
            }}
          >
            {z.zoneId.replace("ZONE-", "")}
          </Link>
        ))}
      </div>

      <div className="pageHeader" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1>{zone.displayName}</h1>
          <p>
            Last updated {timeAgo(zone.state.last_updated)}
            {zone.state.is_stale ? " · data may be stale" : ""}
          </p>
        </div>
        <SourceTag source={live ? "real" : "simulated"} />
      </div>

      <div className="card" style={{ padding: 24, marginBottom: 24 }}>
        <SituationSummary zone={zone} />
      </div>

      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>
          {top ? "Why this zone is risky" : "Zone conditions"}
        </h2>
        <ContributingSignals zone={zone} live={live} />
      </div>

      {zone.riskScore && zone.riskScore.contributors.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>Compound risk</h2>
          <CompoundRiskChain
            contributors={zone.riskScore.contributors.map((c) => ({
              factor_name: c.factor,
              contribution_score: c.score,
              description: c.factor.replace(/_/g, " "),
            }))}
            summary={zone.riskScore.explanation_summary}
          />
        </div>
      )}

      <RelationshipGraph zone={zone} />
    </div>
  );
}
