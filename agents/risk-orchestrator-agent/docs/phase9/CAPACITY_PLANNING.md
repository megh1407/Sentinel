# SENTINEL Risk Orchestrator — Capacity Planning Guide (Phase 9)

> Derived from the registry-documented SLAs (Phase 1 §9.1–§9.4) and this
> component's own per-stage budgets (Phase 2.2 §13.1, Phase 2.3 §14.1,
> Phase 2.4 §13.1). Figures below are sizing *starting points* — the
> benchmark suite (`tests/performance/benchmark_suite.py`) and load tests
> (`tests/load/`) are what validate them against real hardware; this
> document is not a substitute for running those.

## 1. Sizing Model

Per-replica throughput is bounded by whichever of these hits its ceiling first:

| Bound | Limit |
|---|---|
| CPU (Rule Engine's ≤300ms budget dominates) | ~3–5 concurrent zone-cycles/core sustained |
| `RepositoryManager` connection pool (ALDS §5.1, Phase 2.3 §18.3's flagged bottleneck) | `postgres.max_size` × replica count ≤ PostgreSQL's `max_connections` |
| Kafka partition count | inbound topics: 50+20+50+20+50+20 = 210 partitions (Phase 1 §4.7) |

Replica count scales 5→100 on `consumer_lag > 1000` (Phase 1 §9.2) — this
guide estimates the **floor** needed per deployment tier; the HPA (see
`deploy/kubernetes/hpa.yaml`) handles growth beyond it automatically.

## 2. Deployment Tiers

| Tier | Zones | Workers (approx.) | Events/sec (steady) | Replicas (floor→typical peak) |
|---|---|---|---|---|
| **Small site** | ≤ 50 | ≤ 200 | ~20–50 | 5 → 8 |
| **Medium site** | 50–300 | 200–1,500 | ~50–300 | 5 → 20 |
| **Large industrial campus** | 300–2,000 | 1,500–10,000 | ~300–1,500 | 8 → 50 |
| **Multi-site enterprise** | 2,000+ across N sites | 10,000+ | 1,500+ | 20 → 100 (ceiling, Phase 1 §9.2) |

Multi-site does **not** change per-replica compute shape — Section 14.6 of
the Correlation/Rule Engine spec and §13.5 of the Context Builder spec both
establish that per-cycle compute is O(1) relative to total plant size, only
proportional to a zone's local neighborhood. Multi-site sizing is therefore
mostly *more replicas*, not a different topology.

## 3. Per-Component Sizing

### 3.1 Compute (per replica)

| Resource | Small | Medium | Large | Enterprise |
|---|---|---|---|---|
| CPU request | 500m | 500m | 750m | 1 |
| CPU limit | 2 | 2 | 3 | 4 |
| Memory request | 512Mi | 512Mi | 768Mi | 1Gi |
| Memory limit | 1Gi | 1Gi | 1.5Gi | 2Gi |

(A single zone's `RiskContext` is budgeted at "a few hundred KB" — Phase 2.2
§13.2 — so memory scales with concurrently-held zones per replica, not with
total facility size.)

### 3.2 Kafka

| Setting | Small | Medium | Large | Enterprise |
|---|---|---|---|---|
| Inbound partitions (already fixed by registry, Phase 1 §4.7) | 210 total | 210 total | 210 total | 210 total, or request a partition-count increase via the CI-validated `kafka_topics.yaml` change process |
| `sentinel.risk.score.v1` partitions | 100 (registry default) | 100 | 100 | 100, revisit if replica ceiling (100) is itself the bottleneck |
| Retention (inputs) | 24h (48h maintenance, 72h incident) | same | same | same |

### 3.3 PostgreSQL

| Setting | Small | Medium | Large | Enterprise |
|---|---|---|---|---|
| `max_connections` | 200 | 400 | 800 | 1500+ (or PgBouncer in front) |
| Storage growth/month (permanent tables, PG design §9) | ~5–10 GB | ~30–60 GB | ~150–400 GB | 1TB+/month — plan partition-aligned archival tiering (PG design §8, §9.1) |
| Read replica for reporting queries | optional | optional | recommended | required |

### 3.4 Redis

| Setting | Small | Medium | Large | Enterprise |
|---|---|---|---|---|
| Memory | 1–2 GB | 4–8 GB | 16–32 GB | Redis Cluster, sharded (ALDS §9.4's flagged future lever) |
| Eviction policy | `allkeys-lru` | same | same | same (Redis design §8.2) |

### 3.5 Neo4j

| Setting | Small | Medium | Large | Enterprise |
|---|---|---|---|---|
| Heap | 2 GB | 4 GB | 8 GB | 16 GB+, read-replica fan-out (ALDS §9.4) |
| Node/relationship count (rough, per Neo4j design §2/§3) | 10³–10⁴ | 10⁴–10⁵ | 10⁵–10⁶ | 10⁶+ |

## 4. Validating These Numbers

Before trusting any figure above for a real deployment:

1. Run `tests/load/load_test_scenarios.py` at the target tier's events/sec.
2. Run `tests/load/stress_test.py`'s `StressTestEvaluator.document_breaking_point`
   across a load ramp to find the *actual* safe ceiling for the provisioned
   hardware — not the estimate above.
3. Confirm `tests/performance/benchmark_suite.py`'s P99 assertions hold at
   that load level, not just at idle.

This guide is a starting point for procurement conversations, not a
substitute for the measured numbers those three steps produce.
