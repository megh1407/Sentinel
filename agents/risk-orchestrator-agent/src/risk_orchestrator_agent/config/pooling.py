"""
Connection pool configuration — Phase 9 performance tuning.

These are *value objects* consumed by memory/repository_manager.py and its
three adapters at construction time (ALDS §2.5's Configuration Injection
pattern) — this module holds no live connections itself and performs no I/O.
Sizing rationale is documented per-field since pool sizing is one of the more
consequential, least-obvious tuning knobs in the whole system (Phase 2.3
§18.3 and ALDS §15.7 both flag RepositoryManager's pool as a likely future
bottleneck).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresPoolConfig:
    min_size: int = 5
    max_size: int = 25
    timeout_ms: int = 2000
    statement_timeout_ms: int = 150   # a few multiples below the ≤50ms/call
                                       # budget's reasonable ceiling (PG design §13.1)
    idle_timeout_s: int = 300
    max_lifetime_s: int = 1800
    health_check_interval_s: int = 30

    def validate(self) -> None:
        if self.min_size > self.max_size:
            raise ValueError("PostgresPoolConfig.min_size must be <= max_size")
        if self.max_size * 100 > 10_000:
            # 100 replicas x max_size must stay within a realistic PostgreSQL
            # max_connections ceiling (ALDS §13.1) — this is a sanity guard,
            # not a hard platform limit.
            raise ValueError(
                "PostgresPoolConfig.max_size too large for the 100-replica "
                "ceiling (Phase 1 §9.2) — would risk exceeding PostgreSQL's "
                "max_connections at full fleet scale-out"
            )


@dataclass(frozen=True)
class RedisPoolConfig:
    max_size: int = 50
    timeout_ms: int = 50            # this is a cache, not a durable store —
                                     # slow beats stuck, but stuck is unacceptable
                                     # (Redis Integration Design §11)
    idle_timeout_s: int = 60
    health_check_interval_s: int = 15
    retry_max_attempts: int = 3
    retry_backoff_base_ms: int = 20

    def validate(self) -> None:
        if self.timeout_ms > 200:
            raise ValueError(
                "RedisPoolConfig.timeout_ms too high for a cache-tier call — "
                "would erode the ≤150ms ContextBuilder budget (Phase 2.2 §13.1)"
            )


@dataclass(frozen=True)
class Neo4jPoolConfig:
    max_size: int = 20
    timeout_ms: int = 150
    idle_timeout_s: int = 120
    connection_acquisition_timeout_s: int = 5
    max_transaction_retry_time_s: int = 15

    def validate(self) -> None:
        if self.timeout_ms > 150:
            raise ValueError(
                "Neo4jPoolConfig.timeout_ms exceeds the enrichment-path "
                "budget (Phase 2.2 §13.1 / Phase 2.3 §14.1) — Neo4j must "
                "degrade to structural-only correlation before this matters "
                "(Phase 2.3 §13), so this timeout should stay conservative"
            )


@dataclass(frozen=True)
class WorkerPoolConfig:
    """
    Governs application/worker_pool.py's bounded concurrency for CPU-bound
    domain-service execution (RuleEngine, RiskScorer, DecisionEngine —
    Phase 2.1 §9.1's pure-function classification). This does NOT replace
    the platform's shared async runtime (ALDS §9.2) — it bounds how many
    scoring cycles run truly concurrently within one replica, protecting
    the event loop from unbounded fan-out under a burst of inbound events.
    """

    size: int = 32
    max_concurrent_zones: int = 256
    queue_max_size: int = 2048
    task_timeout_s: float = 2.0   # generous slack above the 1.5s total budget

    def validate(self) -> None:
        if self.max_concurrent_zones < self.size:
            raise ValueError(
                "WorkerPoolConfig.max_concurrent_zones must be >= size, since "
                "concurrency is bounded by whichever limit is reached first"
            )


@dataclass(frozen=True)
class ConnectionPoolSettings:
    """Aggregate settings object — this is what agent.py's composition root
    (FRS §2.2) resolves once from config/environment.py and injects into
    RepositoryManager (Phase 3.1 §3.4's dependency-inversion seam)."""

    postgres: PostgresPoolConfig = PostgresPoolConfig()
    redis: RedisPoolConfig = RedisPoolConfig()
    neo4j: Neo4jPoolConfig = Neo4jPoolConfig()
    worker_pool: WorkerPoolConfig = WorkerPoolConfig()

    def validate(self) -> None:
        self.postgres.validate()
        self.redis.validate()
        self.neo4j.validate()
        self.worker_pool.validate()

    @classmethod
    def from_environment(cls, env: dict[str, str]) -> "ConnectionPoolSettings":
        """Resolve pool settings from process environment (populated by the
        ConfigMap in deploy/kubernetes/configmap.yaml or the Helm chart's
        values.yaml) — never from a live, re-polled config reference
        (ALDS §3.5's atomic-snapshot rule applies here too)."""
        settings = cls(
            postgres=PostgresPoolConfig(
                min_size=int(env.get("POSTGRES_POOL_MIN_SIZE", 5)),
                max_size=int(env.get("POSTGRES_POOL_MAX_SIZE", 25)),
                timeout_ms=int(env.get("POSTGRES_POOL_TIMEOUT_MS", 2000)),
                statement_timeout_ms=int(env.get("POSTGRES_STATEMENT_TIMEOUT_MS", 150)),
            ),
            redis=RedisPoolConfig(
                max_size=int(env.get("REDIS_POOL_MAX_SIZE", 50)),
                timeout_ms=int(env.get("REDIS_TIMEOUT_MS", 50)),
            ),
            neo4j=Neo4jPoolConfig(
                max_size=int(env.get("NEO4J_POOL_MAX_SIZE", 20)),
                timeout_ms=int(env.get("NEO4J_TIMEOUT_MS", 150)),
            ),
            worker_pool=WorkerPoolConfig(
                size=int(env.get("SCORING_WORKER_POOL_SIZE", 32)),
                max_concurrent_zones=int(env.get("SCORING_MAX_CONCURRENT_ZONES", 256)),
            ),
        )
        settings.validate()
        return settings
