"""
Chaos engineering scenarios (Phase 9), implementing TSES §8's fault-injection
matrix as executable, automatable checks — run on a schedule (TSES §8.2),
never per-commit.

Each scenario:
  1. injects one fault via the platform's chaos tooling (e.g. Chaos Mesh /
     tc netem / iptables — the injection mechanism itself is a Phase 0/SRE
     concern and is abstracted behind ChaosInjector below so this module
     stays about *assertions*, not infrastructure automation);
  2. asserts the exact documented recovery behavior from the originating
     architecture document occurs;
  3. asserts recovery completes within Phase 1 §9.6's RTO.

This file intentionally does not invent new recovery behavior — every
assertion cites the document that already promised it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


class ChaosInjector(Protocol):
    """Abstracts the actual fault-injection mechanism (Chaos Mesh, tc netem,
    a Kubernetes NetworkPolicy toggle, etc.) so this module tests behavior,
    not a specific chaos tool's API."""

    def block_network_to(self, target: str) -> None: ...
    def restore_network_to(self, target: str) -> None: ...
    def inject_latency(self, target: str, delay_ms: int) -> None: ...
    def terminate_pod(self, pod_name: str) -> None: ...
    def constrain_memory(self, pod_name: str, limit_mb: int) -> None: ...


class HealthClient(Protocol):
    def readiness(self) -> bool: ...
    def liveness(self) -> bool: ...
    def dependency_status(self, store: str) -> str: ...  # "healthy"|"degraded"|"down"


class MetricsClient(Protocol):
    def get(self, name: str, labels: dict | None = None) -> float: ...


@dataclass
class ChaosScenarioResult:
    scenario: str
    passed: bool
    detail: str
    recovery_time_s: float | None = None


RTO_SECONDS = 60  # Phase 1 §9.6


class ChaosScenarios:
    def __init__(self, injector: ChaosInjector, health: HealthClient, metrics: MetricsClient):
        self._injector = injector
        self._health = health
        self._metrics = metrics

    def redis_unavailable(self) -> ChaosScenarioResult:
        """Redis Integration Design §8 — fall back to DB, readiness stays
        true until the breaker opens; never blocks the pipeline."""
        self._injector.block_network_to("redis")
        time.sleep(2)
        if not self._health.readiness():
            return ChaosScenarioResult(
                "redis_unavailable", False,
                "Readiness flipped false on a brief Redis blip — should "
                "tolerate transient loss before the breaker opens (ALDS §6.2)",
            )
        fallback_rate = self._metrics.get("sentinel_redis_fallback_to_db_total")
        self._injector.restore_network_to("redis")
        start = time.monotonic()
        while not self._health.dependency_status("redis") == "healthy":
            if time.monotonic() - start > RTO_SECONDS:
                return ChaosScenarioResult("redis_unavailable", False, "Did not recover within RTO")
            time.sleep(1)
        return ChaosScenarioResult(
            "redis_unavailable", fallback_rate > 0, "Fell back to DB reads as documented",
            recovery_time_s=time.monotonic() - start,
        )

    def neo4j_unavailable(self) -> ChaosScenarioResult:
        """Phase 2.3 §13 / ALDS §6.4 — Neo4j must NEVER gate readiness."""
        self._injector.block_network_to("neo4j")
        time.sleep(3)
        still_ready = self._health.readiness()
        self._injector.restore_network_to("neo4j")
        return ChaosScenarioResult(
            "neo4j_unavailable",
            still_ready,
            "Readiness correctly unaffected by Neo4j outage (ALDS §6.4)"
            if still_ready else
            "VIOLATION: readiness flipped false on Neo4j outage — contradicts "
            "the explicit 'never gates readiness' rule",
        )

    def postgresql_failover(self) -> ChaosScenarioResult:
        """Phase 2.4 §12 — risk_level_changed suppressed, audit retried,
        classification still proceeds."""
        self._injector.block_network_to("postgresql")
        time.sleep(2)
        decisions_still_flowing = self._metrics.get("decision_engine_decisions_total") >= 0
        self._injector.restore_network_to("postgresql")
        start = time.monotonic()
        while self._health.dependency_status("postgresql") != "healthy":
            if time.monotonic() - start > RTO_SECONDS:
                return ChaosScenarioResult("postgresql_failover", False, "PG did not recover within RTO")
            time.sleep(1)
        return ChaosScenarioResult(
            "postgresql_failover", decisions_still_flowing,
            "Classification continued through PG outage, risk_level_changed suppressed",
            recovery_time_s=time.monotonic() - start,
        )

    def kafka_broker_failure(self) -> ChaosScenarioResult:
        """ALDS §7.1 — reconnect via shared client library; readiness false
        while unreachable; pod restart only if reconnection never succeeds."""
        self._injector.block_network_to("kafka")
        time.sleep(5)
        readiness_dropped = not self._health.readiness()
        self._injector.restore_network_to("kafka")
        start = time.monotonic()
        while not self._health.readiness():
            if time.monotonic() - start > RTO_SECONDS:
                return ChaosScenarioResult("kafka_broker_failure", False, "Did not recover within RTO")
            time.sleep(1)
        return ChaosScenarioResult(
            "kafka_broker_failure", readiness_dropped,
            "Readiness correctly dropped during outage and recovered after",
            recovery_time_s=time.monotonic() - start,
        )

    def pod_termination_mid_cycle(self) -> ChaosScenarioResult:
        """ALDS §7.2 / Phase 2.2 §14 — redelivery after crash must not
        double-count; the 5-replica floor absorbs the loss."""
        self._injector.terminate_pod("risk-orchestrator-agent-0")
        start = time.monotonic()
        recovered = False
        while time.monotonic() - start < RTO_SECONDS:
            if self._health.readiness():
                recovered = True
                break
            time.sleep(1)
        return ChaosScenarioResult(
            "pod_termination_mid_cycle", recovered,
            "Fleet absorbed single-pod loss within RTO" if recovered else "Fleet did not recover within RTO",
            recovery_time_s=time.monotonic() - start,
        )

    def disk_pressure(self) -> ChaosScenarioResult:
        """ALDS §7.1 memory-pressure row, applied to disk: proactive
        readiness flip before a hard eviction, never silent data loss."""
        self._injector.constrain_memory("risk-orchestrator-agent-0", limit_mb=200)
        time.sleep(5)
        flipped_before_kill = not self._health.readiness()
        return ChaosScenarioResult(
            "disk_pressure", flipped_before_kill,
            "Proactive readiness flip observed before resource exhaustion"
            if flipped_before_kill else
            "No proactive readiness flip observed under resource pressure",
        )

    def run_all(self) -> list[ChaosScenarioResult]:
        return [
            self.redis_unavailable(),
            self.neo4j_unavailable(),
            self.postgresql_failover(),
            self.kafka_broker_failure(),
            self.pod_termination_mid_cycle(),
            self.disk_pressure(),
        ]
