import { PermitAnalysis } from "@/lib/contracts";
import { AlertCircle, CheckCircle2 } from "lucide-react";

export default function PermitCard({ permit }: { permit: PermitAnalysis }) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        padding: 16,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "0.05em", color: "var(--text-tertiary)" }}>
            {permit.permit_type.toUpperCase()}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{permit.zone_id}</div>
        </div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "3px 8px",
            borderRadius: 5,
            background: permit.status === "active" ? "var(--risk-normal-soft)" : "var(--surface-sunken)",
            color: permit.status === "active" ? "var(--risk-normal)" : "var(--text-secondary)",
          }}
        >
          {permit.status.toUpperCase()}
        </span>
      </div>

      <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginTop: 10 }} className="mono">
        {permit.valid_from} — {permit.valid_to}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginTop: 12,
          fontSize: 12.5,
          fontWeight: 600,
          color: permit.zone_compatibility ? "var(--risk-normal)" : "var(--risk-warning)",
        }}
      >
        {permit.zone_compatibility ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
        {permit.zone_compatibility ? "Compatible with current conditions" : "Review required"}
      </div>

      {!permit.zone_compatibility && permit.recommendations[0] && (
        <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.5 }}>
          {permit.recommendations[0]}
        </p>
      )}

      {permit.conflicts.length > 0 && (
        <div style={{ marginTop: 10, fontSize: 12, color: "var(--risk-warning)" }}>
          ⚠ Conflicts with permit {permit.conflicts[0].conflicting_permit_id}
        </div>
      )}
    </div>
  );
}
