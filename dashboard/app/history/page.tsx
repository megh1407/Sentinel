import { feed, zones } from "@/lib/mockData";
import LiveFeed from "@/components/LiveFeed";
import SourceTag from "@/components/SourceTag";

export default function HistoryPage() {
  const sorted = [...feed].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <div>
      <div className="pageHeader">
        <h1>Event History</h1>
        <p>Chronological record of zone and site events.</p>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <SourceTag source="real" />
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
          zone_intelligence_agent anomalies
        </span>
        <span style={{ marginLeft: 16 }} />
        <SourceTag source="simulated" />
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
          demo events for unimplemented agents
        </span>
      </div>

      <div className="card" style={{ padding: "6px 20px" }}>
        <LiveFeed items={sorted} />
      </div>
    </div>
  );
}
