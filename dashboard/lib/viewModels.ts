import { ZoneRecord, RiskLevel, PlantOverallState } from "./contracts";

/** Unified 5-level status vocabulary used everywhere in the UI. */
export type Status = "NORMAL" | "WATCH" | "WARNING" | "CRITICAL" | "EMERGENCY";

/**
 * Zone risk level (real, from ZoneState.current_risk_level) mapped to the
 * plant-wide status vocabulary used in the Command Center. Isolated here so
 * it is a one-line change when the Risk Orchestrator becomes authoritative
 * (Section 6A / 18 of the brief).
 */
export function zoneStatus(level: RiskLevel): Status {
  switch (level) {
    case "LOW":
      return "NORMAL";
    case "MEDIUM":
      return "WATCH";
    case "HIGH":
      return "WARNING";
    case "CRITICAL":
      return "CRITICAL";
    case "LOCKDOWN":
      return "EMERGENCY";
  }
}

export function plantStatusFromZones(zoneList: ZoneRecord[]): Status {
  const statuses = zoneList.map((z) => zoneStatus(z.state.current_risk_level));
  if (statuses.includes("EMERGENCY")) return "EMERGENCY";
  if (statuses.includes("CRITICAL")) return "CRITICAL";
  if (statuses.includes("WARNING")) return "WARNING";
  if (statuses.includes("WATCH")) return "WATCH";
  return "NORMAL";
}

export function siteOverallToStatus(s: PlantOverallState): Status {
  switch (s) {
    case "normal":
      return "NORMAL";
    case "elevated":
      return "WATCH";
    case "emergency":
    case "evacuating":
      return "EMERGENCY";
    case "shutdown":
    case "lockdown":
      return "EMERGENCY";
  }
}

export const statusColor: Record<Status, string> = {
  NORMAL: "var(--risk-normal)",
  WATCH: "var(--risk-watch)",
  WARNING: "var(--risk-warning)",
  CRITICAL: "var(--risk-critical)",
  EMERGENCY: "var(--risk-emergency)",
};

export const statusSoftColor: Record<Status, string> = {
  NORMAL: "var(--risk-normal-soft)",
  WATCH: "var(--risk-watch-soft)",
  WARNING: "var(--risk-warning-soft)",
  CRITICAL: "var(--risk-critical-soft)",
  EMERGENCY: "var(--risk-emergency-soft)",
};

export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export function activeAnomaly(zone: ZoneRecord) {
  return zone.anomalies.sort((a, b) => {
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return order[a.severity] - order[b.severity];
  })[0];
}
