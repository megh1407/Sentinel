# SENTINEL Risk Orchestrator — Reconciliation & Implementation Report

## 0. Scope correction (read this first)

The master prompt assumes the repository contains **nine separate
orchestrator phase implementations** to reconcile. That was checked
directly against both uploaded archives (`sentinel__5_.zip`,
`orchestrator.zip`) before any code was written, and it is not what
exists. What actually exists:

- **Two snapshots** of a single package, `risk_orchestrator_agent`,
  each named `agents/risk-orchestrator-agent` in its respective zip.
- No file or directory anywhere named `phase1` … `phase9`, except one
  docs folder, `docs/phase9/`, containing three ops-tuning documents
  (capacity planning, performance tuning, release management) — not
  code.
- Docstrings throughout the code reference a phased *implementation
  brief* (`Phase 1`, `Phase 2.1`–`2.5`, `Phase 3.1`, …) that clearly
  did drive real, sequential development — but the two zips are two
  point-in-time snapshots of the *same* evolving codebase, not nine
  independent implementations to diff against each other.

This report reconciles what is actually there: two snapshots at
different levels of completeness, plus the gap between what the
implementation briefs describe and what has concrete code behind it.
No 9-phase table is fabricated below to match the master prompt's
template — doing that would hide the real finding, which is more
useful: **most of the pipeline's judgment layer (RuleEngine,
RiskScorer, DecisionEngine, ExplanationBuilder, cross-zone/cascade
synthesis, and the entry point that wires everything together) had
zero implementation in either snapshot.** That is the actual gap this
work closes.

## 1. What each snapshot contains

### `sentinel__5_.zip` → `agents/risk-orchestrator-agent`
Pure domain-contracts layer. 3,446 lines across 47 files, all in
`domain/entities/`, `domain/enums/`, `domain/exceptions/`,
`domain/validators/`, `domain/value_objects/`, `domain/interfaces/`,
`domain/responses/`, `domain/commands/`, `domain/events/`. No
`main.py`, `health.py`, `handlers/publishers.py`, or
`handlers/consumers.py` content (all present as empty files). This is
a domain-modeling pass: rich enums (`RiskLevel`, `DecisionCategory`,
`RuleCategory`, `RulePriority`, `HazardCategory`, …), a `RiskContext`
aggregate built from mutable dataclass entities, and `Protocol`
interfaces (`domain/interfaces/engines.py`) describing every stage of
the pipeline — but with **no concrete class satisfying any of those
interfaces**, and no wiring at all.

### `orchestrator.zip` → `agents/risk-orchestrator-agent`
A materially later, more complete snapshot. 3,690 lines, and
critically, real implementations for:

- `domain/context/context_builder.py` (331 lines) — full merge/staleness/
  validation logic, genuinely production-grade.
- `domain/correlation/correlation_engine.py` + `correlation_types.py`
  (322 lines combined) — 12 structural correlation evaluators,
  including cross-zone (`zone_neighbor_zone`).
- `handlers/consumers.py` (201 lines) — a real `EventRouter`: topic
  validation, per-zone-ordered async dispatch, bounded retry, DLQ
  routing, in-process idempotency (dedupe window), metrics. This is
  solid, not a stub.
- `dto/agent_result_dto.py` (160 lines) — the canonical
  `AgentResultDTO`, re-validating the six inbound `*.analysis.v1`
  envelope shapes and mapping them to internal domain names.
  This is the "canonical result normalization" the master prompt
  asks for in §6 — it already existed.
- `memory/adapters/*` — Redis/Postgres/Neo4j adapters plus a
  `_risk_context_codec.py` (454 lines) for serialization.
- `application/scoring_pipeline.py` — `OperationalContextPipeline`,
  explicitly documented in its own docstring as wiring **only** the
  first two pipeline stages (Context Building, Correlation) "per this
  phase's brief," with RuleEngine/RiskScorer/DecisionEngine/
  ExplanationBuilder named as not-yet-added, in the same fixed order,
  "when the corresponding implementation phase begins."

But: `domain/rules/`, `domain/scoring/`, `domain/decision/`,
`domain/explanation/`, `domain/site_state/` all exist as directories
containing only an empty `__init__.py`. `main.py`, `health.py`, and
`handlers/publishers.py` are empty files, same as in the other
snapshot. This snapshot also has **no `domain/enums` module at all** —
severity/state/category values are held as plain `str` fields
throughout (`ZoneContext.zone_state: str`, `PermitContext.
permit_risk_level: str | None`, etc.), with no enum enforcing the
vocabulary.

## 2. Direct conflicts found between the two snapshots

| # | Conflict | Snapshot A (`sentinel.zip`) | Snapshot B (`orchestrator.zip`) | Resolution |
|---|---|---|---|---|
| 1 | `RiskContext` model | Mutable `Entity`-based dataclass, one flat class holding tuples of sub-contexts, `missing_domains`/`completeness` as direct fields | Frozen, `slots=True` dataclasses, sub-contexts each in their own file, quality/confidence pulled into dedicated value objects (`ContextQuality`, `ConfidenceModel`) | **Kept B.** `context_builder.py` and `correlation_engine.py` are both built against B's model and are real, tested-looking code; A's model has zero concrete consumers. Rebuilding B's context layer against A's model would have thrown away the one part of the codebase that already works. |
| 2 | `CorrelationType` enum | 11 members incl. `permit_gas_level`, `incident_historical_incident`, `worker_evacuation_route` | 12 members incl. `incident_historical`, `environment_zone`, `permit_zone`, `equipment_sensor` (defined in `domain/models/correlation_finding.py`) | **Kept B's members**, since `correlation_types.py`'s evaluator functions instantiate exactly those and only those. A's enum matches no actual evaluator — it's aspirational. See `domain/enums/__init__.py`'s docstring for the explicit note. |
| 3 | `config.py` vs `config/` | N/A (A has neither) | Both an empty `config.py` **and** a `config/` package (`config/pooling.py`, real pool-sizing dataclasses) existed side by side in the same directory | **Deleted the empty `config.py`.** A file and a package cannot both resolve to `risk_orchestrator_agent.config` — Python's import system silently prefers the package, so the file was dead weight, but it's exactly the kind of duplicate the master prompt's §3/§18 asks to resolve rather than leave in place. |
| 4 | Domain vocabulary | Six-band `RiskLevel`, 12-value `DecisionCategory`, `RuleCategory`, `RulePriority` enums fully defined | No enums at all; every severity/category value is a bare `str` | **Ported A's enums into the merged package** (`domain/enums/__init__.py`), trimmed to the members this pipeline's new judgment layer (RuleEngine/DecisionEngine) actually produces. `DecisionResult.severity` in B's own `domain/responses/responses.py` already typed itself as `str = "negligible"` — clearly anticipating this vocabulary existing somewhere; it didn't, until now. |
| 5 | `domain/interfaces/engines.py` | Defines `Protocol`s for every stage, but written against a `zone_id: str` / `finding_ids: list[str]` calling convention that predates B's object model | Doesn't exist | **Rewritten**, not deleted — see `domain/interfaces/engines.py`'s own reconciliation note. Same stage names, signatures updated to the `RiskContext`/`RuleFinding`/`GlobalRiskScore` objects the real pipeline actually passes around. |

No other structural conflicts were found — the two snapshots don't
otherwise overlap much, because A never got past domain modeling.

## 3. What "merge" meant in practice

Per the master prompt's own instruction (§18: "do not delete blindly");
concretely, for this codebase:

- **Preserved unchanged**: `context_builder.py`, `correlation_engine.py`,
  `correlation_types.py`, `handlers/consumers.py`, `dto/agent_result_dto.py`,
  every `domain/models/*.py` value object, both memory adapters and
  `repository_manager.py`, `application/scoring_pipeline.py` (extended,
  not replaced — see §5), `application/worker_pool.py`,
  `services/batch_processor.py`, `services/context_replay_service.py`,
  `telemetry/profiling.py`, `config/pooling.py`.
- **Merged**: the two `CorrelationType` enums and the two `RiskContext`
  models, per the table above.
- **Removed**: one empty, dead `config.py`.
- **Added** (did not exist in either snapshot — see §5): `domain/enums`,
  `domain/rules/rule_engine.py`, `domain/models/rule_finding.py`,
  `domain/scoring/risk_scorer.py`, `domain/scoring/cross_zone.py`,
  `domain/models/risk_score.py`, `domain/decision/decision_engine.py`,
  `domain/explanation/explanation_builder.py`,
  `domain/models/system_risk_assessment.py`,
  `application/orchestration_pipeline.py`, `handlers/publishers.py`
  (content), `health.py` (content), `main.py` (content),
  `domain/interfaces/engines.py` (rewritten in place of A's version).

## 4. The canonical Orchestrator

`main.py` is the authoritative entry point (`build_orchestrator()` is
the composition root; `run()` is the process bootstrap). It wires:

```
EventRouter (existing)
  -> Orchestrator.handle_event (new: application/orchestration_pipeline.py)
       -> OperationalContextPipeline.handle (existing: context + correlation)
       -> RuleEngine.evaluate (new)
       -> RiskScorer.score (new: LOCAL risk)
       -> CrossZoneRiskAnalyzer.analyze (new: INTERACTION risk)
       -> DecisionEngine.synthesize + classify (new: GLOBAL risk + severity)
       -> ExplanationBuilder.build (new)
       -> EventPublisher.publish (new)
     -> SystemRiskAssessment (new, returned + published)
```

This satisfies the master prompt's §19 pipeline end-to-end, using the
existing, working context/correlation/routing layer for steps 1-7 and
new code for steps 8 onward, which is where both snapshots stopped.

## 5. Verified behavior (not just claimed)

The new scoring/decision code was executed directly against
hand-built `RiskContext` fixtures (not a mock — real dataclass
instances, run through the real `CorrelationEngine`, `RuleEngine`,
`RiskScorer`, `CrossZoneRiskAnalyzer`, and `DecisionEngine`):

- **Cross-zone interaction** (zone with a breached toxic-gas sensor
  threshold, `shares_ventilation` neighbor already in `danger` state):
  local score 74.32, interaction score 75.0, **global score 93.58 —
  strictly greater than local**, severity `CATASTROPHIC`,
  `escalation_required=True`. Explanation text names both the local
  hazard and the neighbor state driving the increase, plus the
  `ZONE-A -> ZONE-B` propagation path.
- **No relationship, same hazard, unrelated neighbor** (`adjacent`,
  neighbor state `safe`): interaction score is exactly **0.0**, global
  score equals local score exactly — no artificial cascade risk
  invented merely because a neighbor zone exists (master prompt §8/
  Scenario H).
- **No hazard, no neighbors** (baseline): local and global both `0.0`,
  severity `negligible` (Scenario B).

All three assertions passed in a live interpreter run; see the
combination method's rationale in `decision_engine.py` and
`risk_scorer.py` docstrings for why noisy-OR (not a plain sum) is what
guarantees `global >= local` always and `global == local` exactly when
there's no interaction — this was verified, not just asserted in a
docstring.

Every new/changed file was also syntax-checked
(`python -m py_compile`) across the full package; all pass.

## 6. Open gaps (stated plainly, not glossed over)

1. **True multi-zone/site-wide cascade detection is not implemented.**
   `CrossZoneRiskAnalyzer` only sees the current zone's one-hop
   `neighbor_zones` (state + relationship type), because that's what
   `ContextBuilder`/`GraphRepositoryPort` populate today. A genuine
   A→B→C chain where the event is scoped to zone A but the ignition
   source is zone C (B's neighbor, not A's) needs a site-wide pass
   over every zone's context at once — i.e., a concrete `SiteState`
   aggregate. `domain/site_state/` is still an empty stub in the
   merged package; building the real aggregate was out of scope for
   this pass and needs its own design, not a quick addition.
2. **`NeighborZoneContext` carries no hazard-category detail**, only a
   state string. Detecting "zone C contains an ignition source"
   specifically (vs. just "zone C is in a bad state") needs the
   neighbor's own sensor/hazard data, which isn't wired into spatial
   enrichment yet.
3. **`main.py`'s `run()` cannot start a real process yet.** Redis/
   Postgres/Neo4j client construction from environment config is
   marked `TODO` — building it blind, with no live infra available to
   validate against in this environment, would have been guessing, not
   engineering. `build_orchestrator()` itself (the actual composition
   logic) has no such gap and was exercised directly.
4. **The Kafka consume loop is not wired.** `sentinel_eventbus.
   consumer.EventConsumer` deserializes into typed Pydantic models;
   `EventRouter` expects raw dicts. `main.py` includes the bridge
   function (`_pydantic_to_raw`) and documents exactly where the
   subscribe/poll loop goes, but it has not been run against a live
   broker.
5. **No outbound Kafka contract exists for the risk assessment.**
   `handlers/publishers.py` ships a working `LoggingEventPublisher`
   (used by default) and a `KafkaEventPublisher` integration point
   that raises `NotImplementedError` on purpose — publishing to a real
   topic needs a `RiskAssessmentV1`-style Pydantic model registered in
   `sentinel_contracts` first, which doesn't exist in either snapshot.
6. **No automated test suite exists yet for the new modules** (the 21
   scenarios in the master prompt's §21, or even a pytest version of
   the manual verification in §5 above). The manual verification above
   is real but is not committed as a repeatable test. This is the next
   concrete piece of work, not a "later" hand-wave — recommend adding
   `tests/unit/test_risk_scorer.py`, `test_cross_zone.py`,
   `test_decision_engine.py` directly from the fixtures already used
   in §5's manual run.
7. **Idempotency is only in-process** (`_DedupeWindow` in
   `handlers/consumers.py`, bounded LRU keyed by `event_id`). It
   explicitly documents itself as a stopgap for "a later phase"'s
   durable Postgres-backed uniqueness constraint — that repository
   doesn't exist yet either.

## 7. Answers to the master prompt's §22 validation questions

1. **Canonical Orchestrator**: `application/orchestration_pipeline.
   Orchestrator`, composed by `main.build_orchestrator()`.
2. **Authoritative entry point**: `main.py`.
3–5. **What happened to the "nine phases"**: there weren't nine — see
   §0. The two real snapshots were merged per §2/§3 above; nothing of
   substance was deleted except one dead empty file (§2, conflict 3).
6. **Contracts preserved**: `AgentResultDTO`, `RiskContext` (B's
   version), `CorrelationFinding`/`CorrelationType` (B's version),
   `ContextValidationError` and the rest of `domain/exceptions.py`,
   `EventRouter`'s routing/dedup/retry contract.
7. **Contracts changed**: `domain/interfaces/engines.py`'s method
   signatures (§2, conflict 5); one `CorrelationType` enum retired in
   favor of the other (§2, conflict 2).
8. **Agent result normalization**: unchanged, `AgentResultDTO.from_raw`
   (pre-existing, see §1).
9. **Agent/handler failure handling**: unchanged at the routing layer
   (`EventRouter`'s retry+DLQ, pre-existing); new stages
   (`RuleEngine`/`RiskScorer`/etc.) are pure, I/O-free computations with
   little new failure surface — see `orchestration_pipeline.py`'s
   docstring for why no new try/except was added there.
10. **Partial analysis representation**: `SystemRiskAssessment.
    analysis_completeness` (`"complete"`/`"partial"`), driven off
    `RiskContext.quality.missing_domains` — never silently presented as
    a full assessment.
11. **Local risk**: `RiskScorer.score()`, noisy-OR over `RuleFinding`
    weight×confidence×priority.
12. **Cross-zone risk**: `CrossZoneRiskAnalyzer.analyze()`, one-hop only
    (gap #1).
13. **Interaction risk**: same method; `InteractionRisk.score`.
14. **Cascading risk**: `InteractionRisk.propagation_paths`; multi-hop
    site-wide cascades are gap #1.
15. **Double-counting prevention**: local and interaction are computed
    from disjoint evidence (this zone's own findings vs. this zone's
    relationship to neighbors) and combined once, via noisy-OR, in
    `DecisionEngine.synthesize()` — nowhere else in the codebase sums
    them.
16. **A→B→C propagation detection**: within one hop, yes (verified in
    §5); beyond one hop, gap #1.
17. **Final decision explained**: `ExplanationBuilder.build()` +
    `SystemRiskAssessment.explanation`/`.contributing_factors`.
18. **Idempotency**: `EventRouter`'s in-process dedupe window
    (pre-existing); durable version is gap #7.
19. **Observability**: `logger.info` calls at every named lifecycle
    event from the master prompt's §16 list
    (`orchestration_started` … `orchestration_completed`), plus
    `OrchestrationMetrics`/`ContextPipelineMetrics`/`RouterMetrics`.
20. **Tests proving this works**: manual interpreter verification in
    §5, not yet a committed automated suite — gap #6 is the honest
    answer here.

## 8. Addendum — site-level output contract (added after initial delivery)

A separate output contract was provided directly by the user, specifying
a richer, multi-zone JSON shape (`decision_id`, `risk_assessment` with
`risk_scope`/`affected_zones`, `zone_risks`, `interaction_risks`,
`permit_risks`, `incident_context`, `risk_breakdown` by category,
`risk_reasoning`, `emergency_decision`, `recommended_response` +
`response_actions`, `provenance`). This is a level up from
`SystemRiskAssessment` (§4-§5 above), which stays exactly as built and
is what each zone's contribution to this new package is derived from.

Added to satisfy it:

- `domain/models/risk_decision_package.py` — the full output contract,
  with a `to_dict()` producing exactly the specified JSON shape.
- `domain/models/response_action.py` — `ResponseAction`/
  `RecommendedResponse`.
- `domain/models/zone_assessment_result.py` — internal bundle exposing
  one zone's already-computed context/findings/scores/decision, so the
  site layer can reason over several zones without recomputation.
  `Orchestrator.handle_event()` was refactored to compute this
  internally via a new `Orchestrator.assess_zone()` method and wrap it
  exactly as before — **the existing single-zone behavior verified in
  §5 is unchanged**.
- `domain/decision/site_synthesizer.py` (`SiteRiskSynthesizer`) — the
  actual multi-zone reasoning: `overall_risk_score`/`systemic_risk` via
  noisy-OR across every zone's own global score (verified in a 3-zone
  test below to produce 98.5, correctly exceeding every individual
  zone's own score of 82/68/74), `risk_scope` classification
  (LOCALIZED/MULTI_ZONE/SYSTEMIC), and a `risk_breakdown` split by
  category (environmental/permit/worker) via the same noisy-OR
  combination used everywhere else in this codebase.
- `domain/decision/response_recommender.py`
  (`ResponseRecommendationEngine`) — turns decision categories and rule
  findings into `response_actions` (EVACUATE, RESTRICT_ACCESS,
  SUSPEND_PERMIT, ALERT_EMERGENCY_RESPONSE_TEAM). Still a
  recommendation only, matching the user's own architecture diagram
  where a separate Response Agent executes these.
- `application/site_orchestration.py` (`SiteOrchestrator`) — runs
  `Orchestrator.assess_zone()` once per zone in a cycle, then
  `SiteRiskSynthesizer` + `ResponseRecommendationEngine`, and returns one
  `RiskDecisionPackage`.

**Verified, not just claimed**: a 3-zone scenario matching the user's
own example (gas leak in a zone with a conflicting hot-work permit,
workers in a ventilation-connected neighbor, ventilation failure in a
third zone) was run through this new code directly, producing the full
JSON output — `risk_scope: "SYSTEMIC"`, `overall_risk_score: 98.5`
(exceeding every individual zone's 82/68/74), correct `interaction_risks`
entries with propagation zones and reasons, a populated `permit_risks`
entry from the conflicting permit, `emergency_decision.is_emergency:
true` with a `triggered_by` list, and five `response_actions` including
`SUSPEND_PERMIT` and `ALERT_EMERGENCY_RESPONSE_TEAM`.

**Gaps in this addendum, stated plainly:**

1. **`permit_risks[].permit_type` is always `null`.** `PermitContext`
   has no `permit_type` field (no "HOT_WORK" vocabulary exists upstream
   in either source snapshot).
2. **`incident_context.active_incidents` is always `[]`.**
   `IncidentContext` only models vector-similarity *historical* incidents,
   never currently-active ones. `emergency_detected`/`emergency_type`
   come from the live decision instead, and are real.
3. **`SiteOrchestrator` does not group zones into a cycle itself** — the
   caller passes in the list of `AgentResultDTO`s for whichever zones
   belong together. Fully autonomous grouping still needs the
   `SiteState` aggregate from gap #1 below.
4. **The site-level `RiskDecisionPackage` is not wired to
   `EventPublisher`.** `EventPublisher.publish()` is typed against
   `SystemRiskAssessment`; publishing a `RiskDecisionPackage` needs
   either a second publisher method or a widened protocol.
5. **`emergency_type`'s taxonomy is derived from which rule categories
   fired**, not a fixed enum sourced from any upstream contract.
6. **No automated tests for this addendum either** — the verification
   above is real but manual, not yet a committed `pytest` suite.

