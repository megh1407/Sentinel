# SENTINEL Risk Orchestrator — Release Management (Phase 9)

## Semantic Versioning

- Image tags follow `MAJOR.MINOR.PATCH` (+ a `-<git-sha>` build suffix for
  traceability), aligned with `context_builder_version` / rule-set version
  metadata already carried on every domain object (Phase 2.2 §5.9, Phase 2.3
  §12.2) — a deployed image version and the config versions it produced
  together fully identify what any historical audit record used.
- **MAJOR**: a breaking change to a published Kafka contract
  (`sentinel.risk.score.v1` / `sentinel.site.state.v1`) — requires the
  30-day dual-write migration window (Phase 1 §4.10), never an in-place change.
- **MINOR**: new rule categories, new correlation types, new configuration
  fields — additive per every predecessor document's Open/Closed extension
  points (Phase 2.1 §13, Phase 2.2 §17, Phase 2.3 §17, Phase 2.4 §17).
- **PATCH**: bug fixes, performance tuning (this phase), no contract or
  schema change.

## Release Checklist

1. All CI/CD gates green (`.github/workflows/risk-orchestrator-cicd.yml`).
2. `tests/performance/benchmark_suite.py` report compared against the prior
   release's — no stage regressed beyond its 10% allowance.
3. `docs/phase9/CAPACITY_PLANNING.md` figures re-validated if this release
   changes per-cycle compute shape (rare — most releases don't).
4. Release notes generated from conventional-commit history since the last
   tag (author-facing, human-reviewed before publish — never auto-published
   without review, consistent with the human-approval principle CSEGS §16.5
   established for the platform generally).
5. Migration scripts (if any PostgreSQL schema change, see PostgreSQL
   Integration §3) reviewed like any other code change (PG design's own
   "migrations are versioned, forward-only, and reviewed" rule, §13.1).

## Deployment Strategies Available

| Strategy | Script | When to use |
|---|---|---|
| Rolling update (default) | `helm upgrade` via CI/CD | Routine PATCH/MINOR releases with no contract change |
| Blue-green | `scripts/deploy-blue-green.sh` | MAJOR releases, or any release the team wants a clean, instant-cutover rollback path for |
| Canary | `scripts/deploy-canary.sh` | Releases touching `RuleEngine`/`RiskScorer` internals (Phase 2.1 §13's ML-model-swap extension point) where a bake period against real traffic is valuable before full rollout |
| Rollback | `scripts/rollback.sh` | Any release exhibiting Section "Chaos Readiness" or benchmark regressions post-deploy |

## Rollback Safety

Because every replica's configuration is versioned and atomically swapped
(ALDS §3.5), and because `RiskAssessment`/`Decision` aggregates are
immutable once written (Phase 2.4 §16.1, Domain Model §3.2), a rollback
never needs to "undo" a decision already published — it only stops a newer
version's code from processing *future* cycles. This is what makes
`scripts/rollback.sh` safe to run without a corresponding data migration in
the overwhelming majority of releases (PATCH/MINOR).
