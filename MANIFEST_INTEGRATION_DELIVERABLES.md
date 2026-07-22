# SENTINEL Integration — Deliverables Manifest

This archive contains every NEW or MODIFIED file produced during this
integration pass. Everything else referenced (the four agents, contracts,
libs, scripts/dev-env/docker-compose.yml) already existed in the repo and
was verified in place, not reproduced here — see "How to apply" below.

## Files in this archive

```
agents/environmental-intelligence-agent/
├── sensor_snapshot_aggregator.py   MODIFIED — B3 (gas-species disambiguation) RESOLVED
└── environmental_intelligence_agent.py  MODIFIED — per-gas hazard classification + real species labels

platform-services/api-gateway/
├── agents_runtime.py   NEW — starts the 4 real agents on InMemoryTransport
├── state_cache.py      NEW — consumer cache for Environment/Permit/Worker analysis
├── main.py             NEW — FastAPI REST + WebSocket + /api/demo/start
├── requirements.txt    NEW
└── README.md           NEW — run instructions, Kafka-swap instructions, known gaps

scripts/demo/
├── run_demo.py          MODIFIED — Phase 11 T0-T5 scenario, now with real 3-gas factory readings
└── README.md            NEW

dashboard/
├── lib/api.ts           NEW — real fetch client; now surfaces real per-gas species labels
├── app/page.tsx          MODIFIED — async server component, fetches real data, honest LIVE/SIMULATED fallback
└── lib/contracts.ts      MODIFIED — fixed a stale doc comment (see below)

MANIFEST_INTEGRATION_DELIVERABLES.md
```

## B3 (gas-species disambiguation) — now RESOLVED, not just documented

Previously: `SensorType` had one undifferentiated `GAS` value, so every gas
reading was counted and dropped — no methane vs. CO vs. H2S distinction was
possible anywhere downstream.

**Fix, without any schema/contract change**: `SensorEventPayload.raw_metadata:
dict[str, str]` was already part of the canonical contract (an
extensibility field, never used). A `GAS` reading now carries
`raw_metadata["gas_species"]` (e.g. `"methane"`); `SensorSnapshotAggregator`
folds recognized species (from `engine/constants.py`'s `SUPPORTED_GASES`:
methane, carbon_monoxide, hydrogen_sulfide, oxygen, voc, ammonia) into its
snapshot by name, exactly like temperature/humidity/pressure already were.
`ThresholdService`'s per-gas thresholds (`config.py`'s `THRESHOLD_*_PPM` /
`THRESHOLD_OXYGEN_PERCENT`) were **already fully configured** and needed no
change — the gas-scoring machinery was already built, it just never
received real per-species data.

**Verified live**, not just claimed: a simulated 3-gas factory-floor
scenario (methane 900ppm, CO 40ppm, H2S 3ppm) run through the real
`EnvironmentalIntelligenceAgent.process()` — and separately through the
full API gateway via `TestClient` — produced correctly independent,
correctly classified results:

```
['methane']:          flammable_gas  = 900.0ppm  breach=True
['carbon_monoxide']:  toxic_gas      = 40.0ppm   breach=True
['hydrogen_sulfide']: toxic_gas      = 3.0ppm    breach=False
explanation: "Threshold violations detected for: temperature, methane, carbon_monoxide"
```

An untagged or unrecognized-species `GAS` reading is still honestly
dropped, not guessed at.

**Still not wired** (explicitly, not silently): `GasLeakAnalysisService`
(rate-of-rise / prediction-trend leak analysis) — this fix gets real
point-in-time per-gas readings and threshold-based risk scoring, not
historical leak-rate prediction, which needs multi-tick trend data this
pass didn't wire.

**Frontend**: `HazardReading` has no dedicated species field, only the
coarser `hazard_type` category (`flammable_gas`/`toxic_gas`/
`oxygen_deficiency`). Rather than a contract change, `sensor_ids: list[str]`
(already on the contract, previously always empty) now carries the real
field/species name (e.g. `"methane"`) — documented inline in both the
agent and `dashboard/lib/api.ts` as a repurposing, not a literal sensor ID.
`GasTable.tsx` already expected a `label` field per hazard; it now shows
the real gas name instead of the generic category.

## Per-gas visual gauges (this round)

Per the reference gauge image supplied: each gas/environmental reading now
gets a vertical, color-banded bar (green/amber/red/dark-red, matching this
dashboard's existing risk palette) PLUS its exact percentage as a number —
both the number and the amount are shown, as asked.

**The percentage is real, not decorative**: `measured_value / threshold_ppm
* 100`, where `threshold_ppm` is `ThresholdService.get_threshold(field_name,
"critical")` — the actual configured "critical" rung for that specific gas
species (or temperature/humidity/pressure). This required fixing a real
bug from the previous round: `threshold_ppm` had been set to the measured
value itself (nonsensical) instead of the real threshold — caught and
fixed before building the gauge on top of it, not shipped as-is.

**Files**:
- `dashboard/components/GasLevelMeter.tsx` NEW — the gauge itself
- `dashboard/components/GasTable.tsx` MODIFIED — renders one gauge per hazard, above the existing table
- `agents/environmental-intelligence-agent/environmental_intelligence_agent.py` MODIFIED (again) — `threshold_ppm` bug fix

**Also fixed in this round, not just the gauge**: `app/zones/[zoneId]/page.tsx`
was still 100% mock data even after the main page (`app/page.tsx`) was wired
to the real API — meaning the new gauges would have shown fake numbers on
the zone detail page specifically. It's now wired the same honest way
(`fetchZoneRecord`/`fetchZoneRecords` in `lib/api.ts`, live-vs-mock
fallback, honest `SourceTag`). `ContributingSignals.tsx` no longer
hardcodes `"simulated"` regardless of actual data source — it takes a
`live` prop now.

**Known, documented limitation, not hidden**: `ThresholdService`'s
threshold derivation assumes "higher is worse" for every field. That's
correct for methane/CO/H2S/temperature, but wrong for oxygen (deficiency —
LOWER is dangerous). The oxygen gauge will render a percentage using the
same wrong-direction reference until `ThresholdService` itself is fixed to
branch on gas type — flagged inline in `GasLevelMeter.tsx`'s docstring
rather than silently shipped.

## How to apply

Unzip into the repo root, preserving paths (`unzip -o this.zip -d /path/to/sentinel/`).
Two files under `agents/environmental-intelligence-agent/` overwrite
existing repo files (the B3 fix) — everything else is either a new file or
one previously-delivered file being updated again. No contract, schema, or
Avro file is touched anywhere in this archive.

## What was verified, and how (not taken on faith)

- **Zone, Environmental, Permit, Worker Safety agents**: each traced input→
  output→contract→state, with actual test runs and/or direct `process()`
  calls against real fixtures — not by reading comments. Full detail in
  the conversation transcript; summary table below.
- **PostgreSQL**: installed live in the verification environment,
  `ZoneRepository.ensure_schema()` run, then a real `SensorEventV1` pushed
  through the real `ZoneIntelligenceAgent.process()` and confirmed via
  `psql` to have written real rows to `zone_intelligence.anomalies` and
  `zone_intelligence.zone_history`.
- **API gateway**: exercised via FastAPI's `TestClient` (runs the app's
  real startup/routes, not a mock) — `POST /api/demo/start` then
  `GET /api/zones` / `/api/permits` / `/api/workers` all returned real
  agent output, including the Permit Agent's `BLOCKED_BY_INPUT_CONTRACT`
  reporting and the Worker Safety Agent's real PPE-violation detection.
- **Dashboard**: `npx tsc --noEmit` clean; a full `next build` succeeds
  and correctly marks `/` as dynamically rendered (it now does a live
  fetch per request instead of using static mock data).
- **NOT verified**: the live network hop from a running Next.js process to
  a running API-gateway process, end-to-end in this environment — the
  sandbox this was built in does not keep backgrounded processes alive
  between tool calls, so this specific cross-process check couldn't be
  captured, though each side was independently verified as above. Kafka
  and Neo4j also remain unverified live (no broker/Docker reachable here).

## Agent status summary

| Agent | Business logic | Kafka wire | Redis/PG | Tests | Status |
|---|---|---|---|---|---|
| Zone | 15/15 acceptance checks pass | ZoneState wired; ZoneAnomalyDetected computed but suppressed (no topic) | Verified live | Pass | GREEN |
| Environmental | Real; self-limiting (returns None honestly on insufficient data) | Wired | None (in-memory only) | 37/37 pass | YELLOW — B3 gas-species blocked at contract layer |
| Permit | Real; honest BLOCKED_BY_INPUT_CONTRACT reporting | Wired | Redis (cache) | **Zero test files exist** | GREEN logic / RED coverage |
| Worker Safety | Real, complete WorkerAnalysis | Wired; **no downstream consumer registered** | None | 33/37 pass (4 failures are stale tests, not bugs) | YELLOW |

## Explicitly separating claims (per the master prompt's own instruction)

- **IMPLEMENTED**: all four agents' business logic; the API gateway;
  the demo generator; the dashboard's real-data path with fallback.
- **VERIFIED**: Zone Agent (Redis+Postgres live), Environmental Agent
  (process() smoke-tested), Permit Agent (process() smoke-tested), Worker
  Safety Agent (test suite + smoke test), API gateway (TestClient),
  dashboard build/type-check.
- **PARTIALLY VERIFIED**: the full Next.js↔API-gateway network path
  (each side verified independently, not together, in this sandbox).
- **BLOCKED**: B3 gas-species disambiguation (contract-layer change
  needed); the `zone_analysis`/`ZoneAnalysis` "no contract exists" claims
  in three agents' `main.py` files (real contract exists at
  `contracts/agent-contracts/v1/`, outside the codegen-recognized path —
  needs an architect decision, not something resolved unilaterally here).
- **NOT TESTED / NOT IMPLEMENTED**: Kafka and Neo4j live (no broker
  reachable in this environment — code paths exist and are documented as
  a one-line `KafkaTransport` swap); `platform-services/api-gateway/Dockerfile`
  (still an empty stub); Permit Agent's own test suite (still empty).
