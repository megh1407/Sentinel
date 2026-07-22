# SENTINEL + Risk Orchestrator — Merge Report

## 1. Final architecture (as actually built and verified, not aspirational)

```
Demo/real sensors
    v
sentinel.sensor.events.v1 / worker.events.v1 / permit.events.v1  (Kafka-equivalent: InMemoryTransport)
    v
Zone / Environmental / Permit / Worker-Safety Agents  (agents_runtime.py — real, verified this integration)
    v
sentinel.zone.state.v1 / environment.analysis.v1 / permit.analysis.v1 / worker.analysis.v1
    v
orchestrator_bridge.py  (NEW — explicit adapter, translates real events -> AgentResultDTO raw envelopes)
    v
risk_orchestrator_agent.handlers.consumers.EventRouter.route()   <- UNMODIFIED orchestrator code
    v
ContextBuilder -> CorrelationEngine -> RuleEngine -> RiskScorer -> CrossZoneRiskAnalyzer
    -> DecisionEngine -> ExplanationBuilder
    v
SystemRiskAssessment
    v
CachingEventPublisher (NEW — in-memory, since no outbound Kafka contract exists yet, see §11 gap #5)
    v
platform-services/api-gateway: GET /api/risk-assessments, /api/risk-assessments/{zone_id}
```

**Response Agent**: not integrated — confirmed empty scaffold (0 lines of code across every file in
`agents/response-agent/`), same as `maintenance-intelligence-agent` and `incident-intelligence-agent`.
The Orchestrator's output is real and available at the REST layer above; nothing consumes it
downstream yet. This matches the original SENTINEL master prompt's explicit scope boundary
("Risk Orchestrator and Response Agent are deliberately absent") — the Response Agent remains
out of scope for this merge too, not silently dropped.

## 2. Responsibility matrix

| SENTINEL component | Responsibility before this merge | Orchestrator's stated responsibility | Final responsibility |
|---|---|---|---|
| Zone Intelligence Agent | Per-zone occupancy/permit/anomaly tracking, publishes `ZoneState` | Consume `ZoneAnalysis` (didn't exist) | Unchanged. `orchestrator_bridge.py` adapts its real `ZoneState` output into the Orchestrator's expected `zone_analysis` shape — Zone Agent itself untouched |
| Environmental Agent | Per-reading hazard/threshold analysis, publishes `EnvironmentAnalysis` | Consume `EnvironmentAnalysis` for local risk | Unchanged, now genuinely feeds the Orchestrator (bridged, not modified) |
| Permit Agent | Permit compliance/conflict analysis, publishes `PermitAnalysis` | Consume `PermitAnalysis` for local risk | Unchanged, now genuinely feeds the Orchestrator |
| Worker Safety Agent | PPE/safety-status analysis, publishes `WorkerAnalysis` | Consume `WorkerAnalysis` for local risk | Unchanged, now genuinely feeds the Orchestrator |
| Maintenance / Incident Agents | **None — empty scaffolds, 0 lines of code** | Consume `MaintenanceAnalysis` / `IncidentAnalysis` | Orchestrator correctly reports these as `missing_domains` on every assessment — not silently treated as "no risk" |
| Risk Orchestrator | Did not exist (empty scaffold, no `main.py`) | Local + interaction + propagation + global risk, one `SystemRiskAssessment` per event | **This is now real** — merged package replaces the scaffold, verified live via `platform-services/api-gateway/orchestrator_runtime.py` |
| Response Agent | Did not exist (empty scaffold) | Consume `SystemRiskAssessment`, decide operational response | **Still does not exist.** Out of scope, confirmed empty, not addressed by this merge |
| API Gateway | Serves zone/permit/worker/environment REST + WebSocket | (not part of original Orchestrator design) | Extended with `orchestrator_runtime.py` (starts the Orchestrator as a 5th real consumer) and two new REST endpoints |

## 3. Canonical contracts

| Concept | Canonical representation | Notes |
|---|---|---|
| Agent result envelope | `risk_orchestrator_agent.dto.agent_result_dto.AgentResultDTO` | The Orchestrator's own canonical inbound shape — **not** changed. The four real agents' Pydantic contracts (`EnvironmentAnalysisV1` etc.) remain canonical for SENTINEL's own internal use; `orchestrator_bridge.py` is the one, explicit, single translation point between the two, per the merge prompt's own rule ("create an explicit adapter only where required") |
| Zone state | `sentinel_contracts.events.zone_state_v1.ZoneStateV1` remains canonical for SENTINEL. `ZoneContext` (Orchestrator's internal domain model) is populated FROM it via the bridge — the Orchestrator's originally-assumed `ZoneAnalysis` contract is **not** created, since no agent produces it and inventing a producer was out of scope (flagged, not fabricated) |
| System-level risk output | `risk_orchestrator_agent.domain.models.system_risk_assessment.SystemRiskAssessment` | New — did not exist before this merge. Exposed at `GET /api/risk-assessments`, matches the master prompt's required field list in full (§ below) |
| Outbound risk-assessment wire contract (`sentinel.risk.assessment.v1`) | **Does not exist yet.** `handlers/publishers.py`'s own docstring states this plainly (gap #5, inherited from `docs/RECONCILIATION_REPORT.md`) | `CachingEventPublisher` (new, this merge) substitutes an in-memory cache until a real Pydantic contract is registered — not a Kafka publish, and not claimed to be one |

`SystemRiskAssessment`'s fields, checked against the master prompt's required output-contract
list — all present: `assessment_id, event_id, correlation_id, site_id, zone_id, computed_at,
global_score, local_risk (global_score.local.score), interaction_risk
(global_score.interaction.score), severity, decision_category, confidence,
contributing_factors, propagation_paths, explanation, escalation_required,
manual_review_required, analysis_completeness, missing_domains, risk_level_changed,
previous_severity`. (Temporal context is folded into `HistoricalContext`/`OperationalTimeline`
inside `RiskContext`, not a separate top-level field — an existing Orchestrator design choice,
preserved rather than changed.)

## 4. Modified files

- `agents/risk-orchestrator-agent/src/risk_orchestrator_agent/**` — the incomplete scaffold
  (domain/entity shapes only, empty `main.py`, no real scoring/decision/explanation logic) was
  **replaced** with the merged, verified 108-file package. This is the one place this merge
  deletes existing code, and it's justified: the scaffold had zero working logic to preserve
  (confirmed by inspection before deleting — `main.py` was 0 bytes).
- `platform-services/api-gateway/main.py` — added Orchestrator startup to the lifespan, added
  `GET /api/risk-assessments` and `GET /api/risk-assessments/{zone_id}`.

## 5. New files

```
platform-services/api-gateway/orchestrator_bridge.py    -- the explicit adapter (event translation + CachingEventPublisher)
platform-services/api-gateway/orchestrator_runtime.py    -- starts the Orchestrator as a real consumer, in its own asyncio thread
```

Plus everything under `agents/risk-orchestrator-agent/` is new relative to the previous empty
scaffold (108 Python files: domain models, ports, adapters, application pipeline, rule engine,
risk scorer, cross-zone analyzer, decision engine, explanation builder, DTOs, handlers, tests,
docs) — all authored in the uploaded package, not by this session; this session's original
contribution is the two bridge files above plus the fixes in §9.

## 6. Removed or deprecated files

- The previous `agents/risk-orchestrator-agent/src/risk_orchestrator_agent/` scaffold tree
  (empty `main.py`, domain-shape-only files with no real logic) — removed, replaced in place.

## 7. Data flow

See §1. Concretely, for one demo tick: a `WorkerEventV1` is published →
`WorkerSafetyAgent.process()` produces a real `WorkerAnalysisV1` → published to
`sentinel.worker.analysis.v1` → `orchestrator_runtime.py`'s consumer receives it →
`orchestrator_bridge.worker_analysis_to_raw()` translates it → `EventRouter.route()` validates
+ dedupes → `Orchestrator.handle_event()` runs the full pipeline → a `SystemRiskAssessment` is
produced and cached → visible immediately at `GET /api/risk-assessments/ZONE-A`.

## 8. Orchestrator flow (internal, unmodified)

`ContextBuilder` (merges the new event into the zone's rolling `RiskContext`, stored in real
Redis via `RedisContextAdapter`) → `CorrelationEngine` → `RuleEngine` (per-domain rule
functions, e.g. `_sensor_hazards`, produce `RuleFinding`s) → `RiskScorer` (local score) →
`CrossZoneRiskAnalyzer` (interaction/propagation — no-op today, since no zone topology/neighbor
data exists yet, honestly reported as `topology_unavailable`/empty propagation paths, not
fabricated) → `DecisionEngine` (severity + decision category) → `ExplanationBuilder` (the
human-readable `explanation` string).

## 9. Real bugs found and fixed during this integration (not shipped silently)

1. **`orchestrator_runtime.py`'s event dispatch used `type(event).__name__`** (`"ZoneStateV1"`)
   instead of the wire `event_type` field (`"ZoneState"`) — silently dropped every event, zero
   assessments produced. Found by running the full pipeline and getting 0 results, not by
   inspection. Fixed.
2. **`environment_analysis_to_raw()` rebuilt an incompatible payload shape**
   (`{gas_readings, hazard_types}`) instead of passing through the real `hazards` list, which
   already matches `parse_sensor()`'s expected shape almost exactly. This silently produced an
   empty `SensorContext.hazards` tuple — no compile error, no exception, just missing
   environmental risk in every assessment. Found by checking *why* gas/temperature breaches
   never appeared in `contributing_factors` despite being real, breached hazards. Fixed —
   after the fix, the demo scenario correctly escalates to `CATASTROPHIC`/`EMERGENCY`
   (score 86.54) instead of `MODERATE`/`warning` (score 51.0).
3. **`permit_analysis_to_raw()` was missing `zone_risk_at_issuance`**, a field `parse_permit()`
   expects and the real `PermitAnalysisV1` payload already carries. Found by cross-checking the
   translator against `parse_permit()`'s actual field list rather than assuming the first
   translator I got right (worker) meant the pattern was safe everywhere. Fixed.
4. **`SystemRiskAssessment.global_score` is a `GlobalRiskScore` object, not a float** — caught
   before shipping by checking the dataclass definition, not by trusting the attribute name.

## 10. Test results

- Orchestrator's own pre-existing unit test suite: **30/30 pass**, run from its new location
  inside the main repo (`PYTHONPATH=src python3 -m pytest tests/unit`).
- No test suite exists for the newly-added judgment layer (`RuleEngine`, `RiskScorer`,
  `DecisionEngine`, `ExplanationBuilder`, `CrossZoneRiskAnalyzer`) — confirmed by directly
  searching for matching test files (none found beyond `test_scoring_pipeline.py`, which only
  covers the older context/correlation stages). This matches `docs/RECONCILIATION_REPORT.md`'s
  own stated gap; not newly introduced by this merge.
- **This merge's own integration path** (bridge + runtime + REST endpoints) has no automated
  test either — verified only by the manual end-to-end runs in this conversation (real demo
  scenario -> real `CATASTROPHIC`/`EMERGENCY` assessment, both via a standalone script and via
  `TestClient` against the real FastAPI app). Writing `tests/integration/test_orchestrator_bridge.py`
  is a natural next step, not done in this pass.
- Single-zone risk, multi-hazard interaction, compound escalation: **verified live** — the demo
  scenario itself IS this test (PPE violation alone -> `MODERATE`; PPE + temperature + methane +
  CO breaches together -> `CATASTROPHIC`/`EMERGENCY`).
- Multi-zone interaction / propagation: **NOT verified** — the demo scenario only ever populates
  one zone (`ZONE-A`); `CrossZoneRiskAnalyzer` has no second zone's data to reason over in this
  pass. Its logic is inherited, verified-by-the-uploaded-package's-own-report, unmodified — but
  not independently re-verified with real cross-zone SENTINEL data here.

## 11. Known limitations (explicit, not hidden)

1. `ZoneState` -> `zone_analysis` is a **bridged, lossy translation**, not the real contract the
   Orchestrator was designed against. `anomalies` is always empty (no real per-zone anomaly data
   exists on the wire anywhere in SENTINEL today — `ZoneAnomalyDetected` is computed but never
   published, a gap from the very first integration pass this session, still unresolved).
2. `maintenance` and `incident` domains are **permanently absent** in this environment — both
   agents are confirmed 0-line scaffolds. Every assessment will report `analysis_completeness:
   "partial"` with these in `missing_domains` until those agents are actually built.
3. **No live Kafka broker** was available to verify against — `InMemoryTransport` throughout,
   same substitution as the rest of this integration, documented as a one-line
   `KafkaTransport` swap per file.
4. **No live Neo4j** — `CrossZoneRiskAnalyzer`'s topology/propagation logic has nothing real to
   query; it correctly reports `topology_unavailable`/empty propagation paths rather than
   fabricating zone relationships, but this means propagation risk is untested against real
   multi-zone data in this environment.
5. **No outbound Kafka contract** for `SystemRiskAssessment` (`sentinel.risk.assessment.v1`
   doesn't exist) — `CachingEventPublisher` is a stand-in, not a claim of real Kafka publication.
6. **Response Agent does not exist** — `SystemRiskAssessment` has a real, verified consumer at
   the REST layer, but nothing acts on `escalation_required`/`decision_category` yet.
7. **No automated tests** for the bridge/runtime integration itself (see §10).

## 12. Future extension points

- A new agent (per the master prompt's "Agent Scalability" section) needs: (1) a real Pydantic
  contract + Kafka topic in `contracts/`, (2) one new translator function in
  `orchestrator_bridge.py` mapping its output into `AgentResultDTO`'s raw shape, (3) one line
  added to `DOMAIN_BY_RESULT_TYPE` in `agent_result_dto.py` if it's a genuinely new domain. The
  Orchestrator's own `RuleEngine`/`RiskScorer`/`ContextBuilder` do not need to change unless the
  new domain needs its own rule function (e.g. a `_noise_hazards` rule) — exactly the
  "reason over standardized results, don't hard-code every agent" property the master prompt asks for.
- Wiring `KafkaTransport` in place of `InMemoryTransport` (one line per call site, same pattern
  already used throughout `agents_runtime.py`/`orchestrator_runtime.py`) is the path to a real
  multi-process deployment.
- Registering a real `sentinel.risk.assessment.v1` contract and swapping
  `CachingEventPublisher` for `KafkaEventPublisher` (already stubbed in `handlers/publishers.py`,
  just raises `NotImplementedError` today) is the path to a real Response Agent integration.
