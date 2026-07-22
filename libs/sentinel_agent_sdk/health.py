"""
health.py

Real health-check registry. Liveness never depends on external
dependencies (a Postgres outage must never cause Kubernetes to kill an
otherwise-healthy process); readiness runs every registered dependency
check. Exposed as plain callables here (not bound to a specific web
framework) so both a FastAPI app and a plain test can use the same logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class HealthStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILING = "FAILING"


@dataclass
class CheckResult:
    name: str
    status: HealthStatus
    message: str = ""


@dataclass
class HealthRegistry:
    _checks: dict[str, Callable[[], bool]] = field(default_factory=dict)
    _process_alive: bool = True

    def register(self, name: str, check_fn: Callable[[], bool]) -> None:
        self._checks[name] = check_fn

    def liveness(self) -> CheckResult:
        """Process-level only. Never runs dependency checks."""
        return CheckResult(
            name="liveness",
            status=HealthStatus.OK if self._process_alive else HealthStatus.FAILING,
        )

    def mark_process_dead(self) -> None:
        """Called only by AgentRunner on an unrecoverable internal failure
        (e.g. the poll loop itself crashes) -- deliberately not exposed for
        agent business logic to call."""
        self._process_alive = False

    def readiness(self) -> tuple[HealthStatus, list[CheckResult]]:
        results = []
        overall = HealthStatus.OK
        for name, check_fn in self._checks.items():
            try:
                ok = check_fn()
                status = HealthStatus.OK if ok else HealthStatus.FAILING
            except Exception as e:  # noqa: BLE001
                status = HealthStatus.FAILING
                results.append(CheckResult(name=name, status=status, message=str(e)))
                overall = HealthStatus.FAILING
                continue
            results.append(CheckResult(name=name, status=status))
            if status == HealthStatus.FAILING:
                overall = HealthStatus.FAILING
        return overall, results

    def register_from_state_container(self, state_container) -> None:
        """Auto-registers exactly the checks relevant to backends the
        agent's StateContainer actually constructed (Part 9's requirement
        that an agent not using Neo4j doesn't get a spurious Neo4j check)."""
        health_snapshot = state_container.health_checks()
        for name in health_snapshot:
            # Late-bind a fresh check per call, not the snapshot value, so
            # readiness reflects CURRENT state each time it's queried.
            self.register(name, self._make_state_check(state_container, name))

    @staticmethod
    def _make_state_check(state_container, name: str) -> Callable[[], bool]:
        def _check() -> bool:
            return state_container.health_checks().get(name, False)
        return _check
