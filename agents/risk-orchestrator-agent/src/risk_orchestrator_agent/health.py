"""health.py — liveness/readiness registry for the Risk Orchestrator (Phase 9).

Empty stub in the merged snapshot even though `main.py` imports
`HealthRegistry` at module load and `register_health_checks()` populates
it. Implemented to exactly the surface `main.py` already uses: register a
named async predicate, then run them all and report per-check pass/fail.

Kept dependency-free (no framework, no HTTP) so importing `main` — which
`build_orchestrator` callers do — never drags in a web server.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

HealthCheck = Callable[[], Awaitable[bool]]

__all__ = ["HealthRegistry"]


class HealthRegistry:
    """Holds named async health checks and evaluates them on demand."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}

    def register(self, name: str, check: HealthCheck) -> None:
        self._checks[name] = check

    @property
    def check_names(self) -> tuple[str, ...]:
        return tuple(self._checks)

    async def run(self) -> dict[str, bool]:
        """Runs every registered check concurrently. A check that raises is
        reported as unhealthy rather than propagating."""
        async def _safe(name: str, check: HealthCheck) -> tuple[str, bool]:
            try:
                return name, bool(await check())
            except Exception:  # noqa: BLE001 — a failing probe is "unhealthy", not a crash
                logger.exception("health_check_raised", extra={"check": name})
                return name, False

        results = await asyncio.gather(
            *(_safe(name, check) for name, check in self._checks.items())
        )
        return dict(results)

    async def is_healthy(self) -> bool:
        results = await self.run()
        return all(results.values()) if results else True
