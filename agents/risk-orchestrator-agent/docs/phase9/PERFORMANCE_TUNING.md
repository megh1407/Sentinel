# SENTINEL Risk Orchestrator — Performance Tuning Guide (Phase 9)

This document explains *how to use* the Phase 9 tooling added to this
codebase — it introduces no new business logic and changes no budget or
contract already fixed by Phases 1–3.4. Every number here is quoted from
an earlier architecture document, never invented.

## 1. What Phase 9 Adds, Precisely

| Addition | File(s) | Purpose |
|---|---|---|
| Stage-level profiling | `telemetry/profiling.py` | Measures each pipeline stage's latency/GC/memory against its already-documented budget; never changes stage output |
| Connection pool tuning | `config/pooling.py` | Typed, validated pool-sizing config injected into `RepositoryManager` at startup (ALDS §2.5) |
| Bounded concurrency | `application/worker_pool.py` | Admission control in front of the existing per-zone task scheduling (ALDS §9.2) — prevents unbounded fan-out under burst load |
| Batched fire-and-forget writes | `services/batch_processor.py` | Micro-batches only the writes already classified as non-critical-path (AuditManager, MetricsCollector) — never the synchronous PostgreSQL transaction (PG Integration §5.2) |
| K8s manifests + Helm chart | `deploy/kubernetes/`, `deploy/helm/` | Deployment topology matching the registry's 5→100 replica policy (Phase 1 §9.2) |
| Load/stress/chaos suites | `tests/load/`, `tests/chaos/` | Proves documented degradation behavior actually occurs (TSES §8) |
| Benchmark suite | `tests/performance/benchmark_suite.py` | Reproducible, release-over-release comparable stage latency reports |
| CI/CD pipeline | `.github/workflows/risk-orchestrator-cicd.yml` | Automates CSEGS §18's staged gates end-to-end |
| Blue-green / canary / rollback scripts | `scripts/` | Safe production rollout mechanics (ALDS §13.3/§13.4) |

## 2. Tuning Order (Cheapest Lever First)

1. **Worker pool size** (`SCORING_WORKER_POOL_SIZE`) — raise until CPU
   utilization approaches the HPA's 70% target (`hpa.yaml`) without
   individual-stage P99s breaching budget in the benchmark suite.
2. **Connection pool sizes** — raise only if `postgres.connection_pool_utilization`
   / `sentinel_redis_connection_health` / Neo4j pool metrics show contention;
   raising blindly risks exceeding each store's own connection ceiling at
   full 100-replica scale-out (`config/pooling.py`'s `validate()` guards this).
3. **Replica floor** — raise the Helm chart's `autoscaling.minReplicas` only
   if a specific deployment tier's steady-state load (see
   `docs/phase9/CAPACITY_PLANNING.md`) exceeds 5 replicas' worth of headroom
   even before any burst.
4. **HPA behavior windows** — `scaleUp.stabilizationWindowSeconds` /
   `scaleDown.stabilizationWindowSeconds` in `values.yaml` — tune only after
   observing real scale-event cadence in staging; the shipped defaults
   (30s up / 300s down) bias toward fast response to lag growth and slow,
   deliberate scale-down to avoid thrash.

## 3. Reading a Benchmark Report

`tests/performance/benchmark_suite.py::test_benchmark_full_cycle_budget_report`
writes a JSON report shaped like:

```json
{
  "total_cycle_ms": {"p50": .., "p95": .., "p99": .., "budget_ms": 1500, "breach_rate": 0.0},
  "stages": {
    "rule_engine": {"p50": .., "p99": .., "budget_ms": 300, "breach_rate": 0.0}
  }
}
```

A non-zero `breach_rate` on any stage is the first place to look before
touching infrastructure sizing — a budget breach concentrated in one stage
(most likely `rule_engine`, per Phase 2.3 §18.3's own flagged pressure
point) usually means the *rule set* has grown, not that the deployment is
under-provisioned. Compare against the previous release's report before
concluding infrastructure is the cause.

## 4. What This Guide Deliberately Does Not Cover

Business-logic correctness (rule semantics, scoring weights, decision
thresholds) is entirely out of scope here — see the Phase 2.1–2.4
architecture documents and `tests/performance` only measures *time*, never
*correctness* (that's `tests/unit` / `tests/integration` / TSES §6's
business-logic validation).
