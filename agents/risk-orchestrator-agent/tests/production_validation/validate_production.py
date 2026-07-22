"""
Final production-validation suite (Phase 9 / TSES §13.1's checklist, made
executable) — run once against a freshly-deployed fleet (or a blue/green
"green" fleet before cutover, see scripts/deploy-blue-green.sh) before it is
trusted with real traffic.

This does not re-run the full test pyramid (Section 2 of TSES already
covers that pre-merge) — it verifies the *deployed, running* system exhibits
the properties those tests already proved in isolation.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import requests


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    detail: str


class ProductionValidator:
    def __init__(self, base_url: str, metrics_url: str):
        self._base_url = base_url.rstrip("/")
        self._metrics_url = metrics_url.rstrip("/")

    def _get(self, path: str, base: str | None = None, timeout: float = 5.0) -> requests.Response:
        return requests.get(f"{(base or self._base_url)}{path}", timeout=timeout)

    def check_service_startup(self) -> ValidationCheck:
        resp = self._get("/healthz")
        return ValidationCheck("service_startup", resp.status_code == 200, f"HTTP {resp.status_code}")

    def check_readiness(self) -> ValidationCheck:
        resp = self._get("/readyz")
        return ValidationCheck("readiness", resp.status_code == 200, f"HTTP {resp.status_code}")

    def check_infrastructure_connectivity(self) -> ValidationCheck:
        # health.py's composite readiness already aggregates Kafka/Redis/
        # PostgreSQL connectivity (ALDS §6.3) — Neo4j deliberately excluded
        # from the gate (ALDS §6.4), so its absence here is correct, not a gap.
        resp = self._get("/readyz")
        ok = resp.status_code == 200
        return ValidationCheck("infrastructure_connectivity", ok, resp.text[:200])

    def check_metrics_exposed(self) -> ValidationCheck:
        resp = self._get("/metrics", base=self._metrics_url)
        required = [
            "risk_orchestrator_stage_latency_ms",
            "context_builder_build_time_ms",
            "rule_engine_rules_fired_total",
            "decision_engine_decisions_total",
        ]
        missing = [m for m in required if m not in resp.text]
        return ValidationCheck(
            "metrics_exposed", not missing,
            "all required metrics present" if not missing else f"missing: {missing}",
        )

    def check_no_vector_db_dependency(self) -> ValidationCheck:
        # ALDS §2.6 / FRS §5.1 — a live check that the running process never
        # reports a Vector DB connectivity signal (one shouldn't exist).
        resp = self._get("/readyz")
        present = "vector_db" in resp.text.lower()
        return ValidationCheck(
            "no_vector_db_dependency", not present,
            "no vector_db signal present, as architecturally required" if not present
            else "VIOLATION: a vector_db health signal was found",
        )

    def check_scaling_headroom(self) -> ValidationCheck:
        resp = self._get("/metrics", base=self._metrics_url)
        # Presence of the HPA-driving metric is what matters here; the actual
        # scale event is exercised by load testing (tests/load), not this suite.
        present = "kafka_consumergroup_lag" in resp.text or "consumer_lag" in resp.text
        return ValidationCheck("scaling_headroom_metric_present", present, "lag metric exported for HPA")

    def run_all(self) -> list[ValidationCheck]:
        checks = [
            self.check_service_startup,
            self.check_readiness,
            self.check_infrastructure_connectivity,
            self.check_metrics_exposed,
            self.check_no_vector_db_dependency,
            self.check_scaling_headroom,
        ]
        results = []
        for check in checks:
            try:
                results.append(check())
            except Exception as exc:  # noqa: BLE001 — report, don't crash the suite
                results.append(ValidationCheck(check.__name__, False, f"exception: {exc}"))
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-deploy production validation")
    parser.add_argument("--namespace", default="sentinel")
    parser.add_argument("--deployment", default="risk-orchestrator-agent")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--metrics-url", default="http://localhost:9090")
    args = parser.parse_args()

    validator = ProductionValidator(args.base_url, args.metrics_url)
    results = validator.run_all()

    print(f"\nProduction Validation — {args.deployment} in {args.namespace}\n" + "=" * 60)
    all_passed = True
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        all_passed &= r.passed
        print(f"[{status}] {r.name}: {r.detail}")

    print("=" * 60)
    print("RESULT:", "ALL CHECKS PASSED" if all_passed else "VALIDATION FAILED — do not cut traffic")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
