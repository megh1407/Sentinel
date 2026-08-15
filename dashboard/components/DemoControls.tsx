"use client";

import { useState } from "react";
import { runScenario, resetDemo } from "@/lib/api";
import { Play, RotateCcw } from "lucide-react";

const SCENARIOS: { id: string; label: string }[] = [
  { id: "normal", label: "Normal" },
  { id: "gas-rise", label: "Single Hazard" },
  { id: "compound-risk", label: "Compound Risk" },
  { id: "multi-zone-emergency", label: "Multi-Zone Emergency" },
];

export default function DemoControls() {
  const [pending, setPending] = useState<string | null>(null);

  async function fire(id: string) {
    setPending(id);
    try {
      await runScenario(id);
    } finally {
      setTimeout(() => setPending(null), 800);
    }
  }

  async function reset() {
    setPending("reset");
    try {
      await resetDemo();
    } finally {
      setTimeout(() => setPending(null), 800);
    }
  }

  return (
    <div
      className="card"
      style={{
        padding: "12px 20px",
        marginBottom: 16,
        display: "flex",
        alignItems: "center",
        gap: 10,
        flexWrap: "wrap",
      }}
    >
      <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        Demo
      </span>
      {SCENARIOS.map((s) => (
        <button
          key={s.id}
          onClick={() => fire(s.id)}
          disabled={pending !== null}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12.5,
            fontWeight: 600,
            padding: "7px 14px",
            borderRadius: 999,
            border: "1px solid var(--border)",
            background: pending === s.id ? "var(--accent-soft)" : "var(--surface)",
            color: pending === s.id ? "var(--accent-strong)" : "var(--text-secondary)",
            cursor: pending !== null ? "default" : "pointer",
            opacity: pending !== null && pending !== s.id ? 0.5 : 1,
          }}
        >
          <Play size={12} />
          {s.label}
        </button>
      ))}
      <button
        onClick={reset}
        disabled={pending !== null}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12.5,
          fontWeight: 600,
          padding: "7px 14px",
          borderRadius: 999,
          border: "1px solid var(--border)",
          background: "var(--surface)",
          color: "var(--text-tertiary)",
          marginLeft: "auto",
          cursor: pending !== null ? "default" : "pointer",
          opacity: pending !== null && pending !== "reset" ? 0.5 : 1,
        }}
      >
        <RotateCcw size={12} />
        Reset
      </button>
    </div>
  );
}
