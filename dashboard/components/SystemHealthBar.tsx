"use client";

import { useEffect, useState } from "react";
import { fetchHealth, HealthStatus } from "@/lib/api";
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";

function Dot({ ok }: { ok: boolean | null }) {
  if (ok === null) return <MinusCircle size={13} color="var(--text-tertiary)" />;
  return ok ? <CheckCircle2 size={13} color="var(--risk-normal)" /> : <XCircle size={13} color="var(--risk-critical)" />;
}

function Item({ label, ok }: { label: string; ok: boolean | null }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5 }}>
      <Dot ok={ok} />
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="mono" style={{ fontWeight: 600, color: ok === null ? "var(--text-tertiary)" : ok ? "var(--risk-normal)" : "var(--risk-critical)" }}>
        {ok === null ? "N/A" : ok ? "Connected" : "Down"}
      </span>
    </div>
  );
}

export default function SystemHealthBar() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          setHealth(h);
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (error) {
    return (
      <div className="card" style={{ padding: "10px 18px", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
        <XCircle size={14} color="var(--risk-critical)" />
        <span style={{ fontSize: 12.5, color: "var(--risk-critical)", fontWeight: 600 }}>
          Backend unreachable — is the api-gateway running on :8000?
        </span>
      </div>
    );
  }

  if (!health) return null;

  const kafkaOk = health.transport_mode === "kafka" ? health.components.kafka : null;

  return (
    <div
      className="card"
      style={{
        padding: "10px 20px",
        marginBottom: 16,
        display: "flex",
        alignItems: "center",
        gap: 22,
        flexWrap: "wrap",
      }}
    >
      <Item label="Redis" ok={health.components.redis} />
      <Item label="PostgreSQL" ok={health.components.postgres} />
      <Item label="Neo4j" ok={health.components.neo4j} />
      <Item label="Kafka" ok={kafkaOk} />
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5 }}>
        <Dot ok={health.agents_active === 4} />
        <span style={{ color: "var(--text-secondary)" }}>Intelligence Agents</span>
        <span className="mono" style={{ fontWeight: 600 }}>
          {health.agents_active}/4 Active
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5 }}>
        <Dot ok={health.orchestrator_active} />
        <span style={{ color: "var(--text-secondary)" }}>Risk Orchestrator</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5 }}>
        <Dot ok={health.response_agent_active} />
        <span style={{ color: "var(--text-secondary)" }}>Response Agent</span>
      </div>
      <span
        className="mono"
        style={{
          marginLeft: "auto",
          fontSize: 11,
          color: "var(--text-tertiary)",
          textTransform: "uppercase",
          letterSpacing: "0.03em",
        }}
      >
        transport: {health.transport_mode}
        {health.transport_mode === "memory" && " (not real Kafka — set SENTINEL_TRANSPORT=kafka)"}
      </span>
    </div>
  );
}
