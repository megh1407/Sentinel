import { WorkerAnalysis } from "@/lib/contracts";
import { HardHat, ShirtIcon, Hand } from "lucide-react";

const violationLabels: Record<string, { icon: React.ElementType; label: string }> = {
  helmet_missing: { icon: HardHat, label: "Helmet" },
  vest_missing: { icon: ShirtIcon, label: "Vest" },
  gloves_missing: { icon: Hand, label: "Gloves" },
};

export default function PPECard({ worker }: { worker: WorkerAnalysis }) {
  const violated = new Set(worker.ppe_violations);
  const items = ["helmet_missing", "vest_missing", "gloves_missing"];

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 14, fontWeight: 600 }} className="mono">
          {worker.worker_id}
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "3px 8px",
            borderRadius: 5,
            background: worker.ppe_violations.length ? "var(--risk-critical-soft)" : "var(--risk-normal-soft)",
            color: worker.ppe_violations.length ? "var(--risk-critical)" : "var(--risk-normal)",
          }}
        >
          {worker.ppe_violations.length ? "PPE VIOLATION" : "COMPLIANT"}
        </span>
      </div>

      <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
        {items.map((key) => {
          const { icon: Icon, label } = violationLabels[key];
          const missing = violated.has(key);
          return (
            <div key={key} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <Icon size={18} color={missing ? "var(--risk-critical)" : "var(--risk-normal)"} />
              <span style={{ fontSize: 10.5, color: "var(--text-secondary)" }}>{label}</span>
              <span
                style={{
                  fontSize: 9.5,
                  fontWeight: 700,
                  color: missing ? "var(--risk-critical)" : "var(--risk-normal)",
                }}
              >
                {missing ? "MISSING" : "DETECTED"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
