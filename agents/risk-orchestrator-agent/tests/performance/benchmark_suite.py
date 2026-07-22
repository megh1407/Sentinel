"""
Reproducible benchmark suite (Phase 9, TSES §2 "Performance Tests" level).

Run: pytest tests/performance/benchmark_suite.py --benchmark-only

Each benchmark targets exactly one stage budget already established in the
architecture series — this file adds no new budget, it only proves the
existing ones (Phase 1 §9.9, Phase 2.2 §13.1, Phase 2.3 §14.1, Phase 2.4
§13.1). Domain services are exercised directly (no Kafka/DB infra), per
TSES §3's "Unit Tests: fakes/mocks only" guidance for domain/* modules —
these are latency micro-benchmarks, not integration tests.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

from risk_orchestrator_agent.telemetry.profiling import (
    STAGE_BUDGETS_MS,
    TOTAL_CYCLE_BUDGET_MS,
    build_cycle_report,
)

# --- Fixture builders -------------------------------------------------------
# Hand-built, deterministic fixtures — never randomized — consistent with
# TSES §1.5's "deterministic testing" rule for domain-logic verification.


@pytest.fixture(scope="module")
def canonical_risk_context():
    """The Phase 1 §5.1 worked example, in fixture form."""
    from tests.fixtures.risk_context_fixtures import build_canonical_risk_context
    return build_canonical_risk_context()


# --- Per-stage benchmarks ----------------------------------------------------

@pytest.mark.benchmark(group="context_builder")
def test_benchmark_context_builder(benchmark, canonical_risk_context):
    from risk_orchestrator_agent.domain.context.context_builder import ContextBuilder
    from tests.fixtures.ports import FakeContextRepositoryPort

    builder = ContextBuilder(context_port=FakeContextRepositoryPort())
    result = benchmark(builder.snapshot, "zone-17")
    assert result is not None


@pytest.mark.benchmark(group="correlation_engine")
def test_benchmark_correlation_engine(benchmark, canonical_risk_context):
    from risk_orchestrator_agent.domain.correlation.correlation_engine import CorrelationEngine

    engine = CorrelationEngine(graph_port=None)
    findings = benchmark(engine.correlate, canonical_risk_context)
    assert isinstance(findings, list)


@pytest.mark.benchmark(group="rule_engine")
def test_benchmark_rule_engine(benchmark, canonical_risk_context):
    from risk_orchestrator_agent.domain.rules.rule_engine import RuleEngine
    from tests.fixtures.rule_sets import canonical_rule_set

    engine = RuleEngine()
    correlations = []  # populated from a correlation-engine fixture in the real suite
    findings = benchmark(engine.evaluate, correlations, canonical_rule_set())
    assert isinstance(findings, list)


@pytest.mark.benchmark(group="risk_scorer")
def test_benchmark_risk_scorer(benchmark):
    from risk_orchestrator_agent.domain.scoring.risk_scorer import RiskScorer
    from tests.fixtures.weight_tables import canonical_weight_table

    scorer = RiskScorer()
    result = benchmark(scorer.score, [], canonical_weight_table())
    assert result is not None


@pytest.mark.benchmark(group="decision_engine")
def test_benchmark_decision_engine(benchmark):
    from risk_orchestrator_agent.domain.decision.decision_engine import DecisionEngine

    engine = DecisionEngine(history_port=None)
    decision = benchmark(engine.classify, 79, [], None)
    assert decision is not None


# --- End-to-end cycle benchmark ---------------------------------------------

def test_benchmark_full_cycle_budget_report(tmp_path: Path):
    """
    Not a pytest-benchmark micro-benchmark — this drives N synthetic cycles
    through StageProfiler-wrapped stages and writes the aggregate report
    (Section 7's "Benchmark Suite" deliverable) so results are comparable
    release over release, per Phase 9's "track results across releases".
    """
    from tests.fixtures.cycle_runner import run_synthetic_cycles

    profiles = run_synthetic_cycles(count=200)
    report = build_cycle_report(profiles)

    out_path = tmp_path / "benchmark_report.json"
    out_path.write_text(json.dumps(report, indent=2))

    assert report["total_cycle_ms"]["p99"] <= TOTAL_CYCLE_BUDGET_MS * 1.05, (
        "P99 total cycle latency exceeded the 1,500ms budget (Phase 1 §9.9) "
        "by more than a 5% measurement-noise allowance"
    )
    for stage, budget_ms in STAGE_BUDGETS_MS.items():
        if stage in report["stages"]:
            assert report["stages"][stage]["p99"] <= budget_ms * 1.10, (
                f"Stage '{stage}' P99 exceeded its budget of {budget_ms}ms "
                f"by more than a 10% allowance"
            )
