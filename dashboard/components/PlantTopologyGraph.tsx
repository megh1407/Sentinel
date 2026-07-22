/**
 * PlantTopologyGraph -- renders the plant's zone relationship graph exactly
 * as it exists in Neo4j (served by the api-gateway at /api/topology). This
 * is backend-derived topology, NOT invented client-side: every node and edge
 * here came from a real Neo4j query. If the gateway/Neo4j isn't reachable it
 * renders nothing rather than a fabricated graph.
 *
 * Async server component -- fetches on the server at request time, same
 * pattern as app/page.tsx's loadDashboardData.
 */
import { fetchTopology } from "@/lib/api";
import SourceTag from "./SourceTag";

const REL_LABEL: Record<string, string> = {
  shares_ventilation: "SHARES VENTILATION",
  adjacent: "ADJACENT",
  evacuation_route: "EVAC ROUTE",
};

export default async function PlantTopologyGraph() {
  let topo;
  try {
    topo = await fetchTopology();
  } catch {
    return null; // Neo4j / gateway not reachable -- show nothing, never fake it
  }
  if (!topo.nodes.length) return null;

  // Collapse the bidirectional seed to one row per undirected pair.
  const seen = new Set<string>();
  const edges = topo.edges.filter((e) => {
    const key = [e.from, e.to].sort().join("|") + "|" + e.relationship_type;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  const statusColor: Record<string, string> = {
    normal: "var(--text-secondary)",
    warning: "var(--risk-warning)",
    critical: "var(--risk-critical)",
    emergency: "var(--risk-critical)",
  };

  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 className="sectionLabel" style={{ margin: 0 }}>
          Zone topology (Neo4j) &mdash; how a hazard propagates
        </h3>
        <SourceTag source="real" />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        {topo.nodes.map((n) => (
          <div
            key={n.zone_id}
            style={{
              border: "1px solid var(--border-strong)",
              borderRadius: 8,
              padding: "6px 12px",
              fontSize: 12.5,
              fontWeight: 600,
              color: statusColor[n.current_status ?? "normal"] ?? "var(--text-secondary)",
            }}
          >
            {n.zone_id}
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", marginLeft: 6 }}>
              {n.current_status ?? "normal"}
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {edges.map((e, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
            <span style={{ fontWeight: 600, minWidth: 60 }}>{e.from}</span>
            <span style={{ color: "var(--text-tertiary)", fontSize: 10.5, letterSpacing: 0.5 }}>
              &mdash;{REL_LABEL[e.relationship_type] ?? e.relationship_type.toUpperCase()}&rarr;
            </span>
            <span style={{ fontWeight: 600, minWidth: 60 }}>{e.to}</span>
            {e.distance_m != null && (
              <span style={{ color: "var(--text-tertiary)", fontSize: 10.5 }}>{e.distance_m}m</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
