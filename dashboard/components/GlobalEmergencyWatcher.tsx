"use client";

/**
 * GlobalEmergencyWatcher -- polls the real Risk Orchestrator / Response
 * Agent output and pops EmergencyOverlay from ANY page, not just /emergency.
 * This is what makes the popup "impossible to miss": it's mounted once in
 * app/layout.tsx, so it's alive no matter which route you're on.
 *
 * Fires only on a genuinely new emergency (tracked by risk_id, not just
 * zone_id) -- acknowledging or dismissing one doesn't suppress the next
 * real one for the same zone.
 */
import { useEffect, useState, useRef } from "react";
import { fetchRiskAssessments, fetchActionRequests } from "@/lib/api";
import { RiskScore } from "@/lib/contracts";
import EmergencyOverlay, { EmergencyActionRequest } from "./EmergencyOverlay";

const POLL_MS = 4000;
const EMERGENCY_SEVERITIES = new Set(["catastrophic", "critical"]);

export default function GlobalEmergencyWatcher() {
  const [active, setActive] = useState<{ zoneId: string; risk: RiskScore; action: EmergencyActionRequest | null } | null>(
    null
  );
  const seenRiskIds = useRef<Set<string>>(new Set());
  const dismissedRiskIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [risks, actions] = await Promise.all([fetchRiskAssessments(), fetchActionRequests()]);
        if (cancelled) return;

        for (const [zoneId, risk] of Object.entries(risks)) {
          const isNew = !seenRiskIds.current.has(risk.risk_id);
          seenRiskIds.current.add(risk.risk_id);

          if (!EMERGENCY_SEVERITIES.has(risk.severity)) continue;
          if (dismissedRiskIds.current.has(risk.risk_id)) continue;
          // Only auto-pop for an assessment we haven't already surfaced, so a
          // page navigation or re-render doesn't re-trigger the same one.
          if (!isNew && active?.risk.risk_id !== risk.risk_id) continue;

          setActive({ zoneId, risk, action: actions[zoneId] ?? null });
          break; // one at a time -- don't stack overlays
        }
      } catch {
        // gateway unreachable -- stay silent, never fabricate an emergency
      }
    }

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!active) return null;

  return (
    <EmergencyOverlay
      zoneId={active.zoneId}
      risk={active.risk}
      action={active.action}
      onDismiss={() => {
        dismissedRiskIds.current.add(active.risk.risk_id);
        setActive(null);
      }}
    />
  );
}
