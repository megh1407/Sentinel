import { zones as mockZones, siteState as mockSiteState, feed as mockFeed } from "@/lib/mockData";
import { fetchZoneRecords, deriveSiteState, deriveFeed } from "@/lib/api";
import { siteOverallToStatus, statusColor } from "@/lib/viewModels";
import { ZoneRecord, SiteState, FeedItem } from "@/lib/contracts";
import StatusPill from "@/components/StatusPill";
import SourceTag from "@/components/SourceTag";
import PlantHeatmap from "@/components/PlantHeatmap";
import PlantTopologyGraph from "@/components/PlantTopologyGraph";
import LiveFeed from "@/components/LiveFeed";
import { Users, Siren } from "lucide-react";

/**
 * Phase 10 wiring: tries the real api-gateway first (see
 * platform-services/api-gateway/README.md for how to run it), and only
 * falls back to lib/mockData.ts's fabricated demo fixtures if that fetch
 * fails -- e.g. the gateway isn't running in this environment. The
 * SourceTag on screen honestly reflects which one happened; it never
 * claims "LIVE" for mock data.
 */
async function loadDashboardData(): Promise<{ zones: ZoneRecord[]; siteState: SiteState; feed: FeedItem[]; live: boolean }> {
  try {
    const zones = await fetchZoneRecords();
    if (zones.length === 0) {
      // Gateway reachable but no zones published yet (demo not started) --
      // still real, just empty. Show mock fixtures so the UI isn't blank,
      // but do NOT claim they're live.
      return { zones: mockZones, siteState: mockSiteState, feed: mockFeed, live: false };
    }
    return { zones, siteState: deriveSiteState(zones), feed: deriveFeed(zones), live: true };
  } catch {
    return { zones: mockZones, siteState: mockSiteState, feed: mockFeed, live: false };
  }
}

export default async function CommandCenter() {
  const { zones, siteState, feed, live } = await loadDashboardData();
  const status = siteOverallToStatus(siteState.overall_state);

  return (
    <div>
      <div className="pageHeader">
        <h1>Command Center</h1>
        <p>Site-wide status, at a glance.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 20, alignItems: "center", marginBottom: 28 }}>
        <div className="card" style={{ padding: "22px 28px", display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <div className="sectionLabel" style={{ marginBottom: 8 }}>Plant status</div>
            <StatusPill status={status} size="lg" pulse />
          </div>
        </div>

        <div className="card" style={{ padding: "18px 24px", display: "flex", gap: 32 }}>
          <Stat label="Workers on site" value={siteState.total_workers} icon={Users} />
          <Stat label="Active incidents" value={siteState.active_incidents} icon={Siren} accent />
          <div>
            <div style={{ fontSize: 11.5, color: "var(--text-tertiary)" }}>Highest risk zone</div>
            <div style={{ fontWeight: 700, fontSize: 15, marginTop: 4, color: statusColor[status] }}>
              {siteState.highest_risk_zone}
            </div>
          </div>
        </div>

        <SourceTag source={live ? "real" : "simulated"} />
      </div>

      <section style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Where is the problem?</h2>
          <SourceTag source={live ? "real" : "simulated"} />
        </div>
        <PlantHeatmap zones={zones} />
      </section>

      <section style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>How could it spread?</h2>
        </div>
        {/* Backend-derived Neo4j topology; renders nothing if unavailable. */}
        <PlantTopologyGraph />
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>What changed recently?</h2>
          <SourceTag source={live ? "real" : "simulated"} />
        </div>
        <div className="card" style={{ padding: "6px 20px" }}>
          <LiveFeed items={feed} />
        </div>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  accent?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <Icon size={18} color={accent ? "var(--risk-warning)" : "var(--text-secondary)"} />
      <div>
        <div style={{ fontSize: 11.5, color: "var(--text-tertiary)" }}>{label}</div>
        <div style={{ fontWeight: 700, fontSize: 18 }} className="mono">
          {value}
        </div>
      </div>
    </div>
  );
}
