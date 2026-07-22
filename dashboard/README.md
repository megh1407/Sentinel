# SENTINEL Dashboard — Command Center Frontend

Next.js 16 / TypeScript / App Router. No CSS framework — design tokens in
`app/globals.css`, Inter + IBM Plex Mono via `@fontsource`.

## Setup

```
npm install
npm run dev
```

## What's real vs simulated (see full audit in chat)

- `lib/contracts.ts` — TypeScript mirrors of the actual backend schemas.
  Types are commented with which are REAL (produced by
  `zone_intelligence_agent`, live-tested) vs SIMULATED (shaped from
  `contracts/agent-contracts/v1/*.schema.json`, which exist but have no
  agent implementation behind them yet).
- `lib/mockData.ts` — the ONLY place demo data is fabricated. Swap this
  module for a real API client (fetch against a future dashboard-service
  REST/WebSocket API) without touching components or pages — that's the
  whole point of the `ZoneRecord` shape matching the real contracts.
- Every card in the UI carries a `LIVE` / `SIMULATED` / `UNAVAILABLE`
  badge (`components/SourceTag.tsx`) so nothing pretends to be live data
  that the backend doesn't actually produce.

## Pages

- `/` — Command Center (plant status, zone heatmap, live feed)
- `/zones/[zoneId]` — Zone detail (situation summary, contributing
  signals, compound-risk explanation, relationship graph)
- `/emergency` — Emergency Center (critical zones, response overlay)
- `/history` — Event History
- `/trace` — System Trace (developer/debug view of what's actually wired)

## Known gaps this UI surfaces rather than hides

- No `api-gateway` exists yet (Dockerfile only) — this app has no live
  backend to call, hence the mock layer.
- `environmental_intelligence_agent.process()` always returns `None` —
  gas readings never reach it and `environment_analysis` has no
  generated model.
- `risk_orchestrator_agent` has domain entities/interfaces only, no
  concrete scoring engine.
- `permit_intelligence_agent`, `worker_safety_agent`,
  `maintenance_intelligence_agent`, `incident_intelligence_agent`,
  `response_agent`, `safety_copilot_agent` have no implementation.

When these land for real, replace `lib/mockData.ts`'s exports with
fetches against the real endpoints — the contracts in `lib/contracts.ts`
are already shaped to match.
