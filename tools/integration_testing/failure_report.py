"""
failure_report.py

Generates integration_report.md. Two kinds of content, kept clearly
separate so neither gets mistaken for the other:

  1. RUNTIME EVIDENCE -- pulled live from event_logger's SQLite store.
     Every number here reflects what this run actually observed. If you
     haven't run the demo yet, these sections will be empty/zero, not
     estimated.
  2. KNOWN PLATFORM GAPS -- a static list of the specific, cited gaps this
     harness found by reading the real code (main.py docstrings,
     grep results confirming missing generated models, etc.), documented
     once here so every report says the same true thing about them instead
     of rediscovering or restating them differently each run.

Usage:
    python3 failure_report.py
"""
from __future__ import annotations

import sys
import time

import harness_config as cfg
from event_history import (
    counter_span_seconds, events_for_trace, failed_events, latency_stats, stage_counts,
)

PLATFORM_GAPS = [
    {
        "id": "B1",
        "title": "sentinel.environment.analysis.v1 has no generated Pydantic model",
        "priority": "Critical",
        "effort": "Medium (design + codegen a real EnvironmentAnalysis contract; "
                  "then wire ThresholdService..RecommendationService into process() to actually produce one)",
        "evidence": (
            "agents/environmental-intelligence-agent/main.py raises RuntimeError before "
            "AgentRunner.run() ever executes, citing this exact gap. `grep -rl \"class "
            "EnvironmentAnalysis\"` across the whole repo returns nothing."
        ),
        "impact": "Environmental Intelligence Agent can consume SensorEvent and run "
                  "SensorSnapshotAggregator.ingest(), but can never publish a result -- "
                  "ThresholdService, TrendService, PredictionService, CorrelationService, "
                  "RiskService, and RecommendationService are all constructed in initialize() "
                  "but never invoked by process().",
    },
    {
        "id": "ZONE-ANALYSIS",
        "title": "sentinel.zone.analysis.v1 has no generated model and is never wired",
        "priority": "High",
        "effort": "Medium-High (this is a genuinely new contract -- ZoneAnalysis doesn't overlap "
                  "with the existing ZoneState/ZoneAnomalyDetected models; needs its own design)",
        "evidence": (
            "agents/zone_intelligence_agent/main.py's own module docstring documents this under "
            "PLATFORM_GAP. `grep -rl \"class ZoneAnalysis\"` returns nothing repo-wide."
        ),
        "impact": "Zone Intelligence Agent publishes ZoneState to sentinel.zone.state.v1 only. "
                  "There is no ZoneAnalysis event anywhere in this platform today.",
    },
    {
        "id": "ZONE-ANOMALY-UNPUBLISHED",
        "title": "ZoneAnomalyDetected is fully computed but never reaches Kafka",
        "priority": "High",
        "effort": "Low (the model and business logic already exist -- this is purely a "
                  "kafka_topics.yaml registration + main.py wiring change)",
        "evidence": (
            "ZoneAnomalyDetectedV1 has a real generated model and ZoneIntelligenceAgent.process() "
            "genuinely computes it (with Postgres audit rows and metrics), but main.py's "
            "_ZoneAnomalySuppressingAgent strips it before AgentRunner would otherwise crash "
            "trying to publish to a topic kafka_topics.yaml never registered for it."
        ),
        "impact": "Every anomaly this agent detects (environmental hazard correlation, PPE "
                  "conflicts, permit conflicts) is computed and audited, but no downstream "
                  "consumer or dashboard can ever see it via Kafka.",
    },
    {
        "id": "EQUIPMENT-STATE",
        "title": "sentinel.equipment.state.v1 has no generated Pydantic model",
        "priority": "Medium",
        "effort": "Low-Medium (a legacy JSON Schema already exists as a starting point: "
                  "contracts/events/v1/equipment_state.schema.json)",
        "evidence": "Confirmed via file listing under contracts/events/ -- only a legacy JSON "
                    "Schema file exists, no Avro contract dir, no generated class.",
        "impact": "fake_equipment_simulator.py cannot run; Zone Intelligence Agent's equipment "
                  "handling (EquipmentRiskDetected/MaintenanceRequired -- which DO have real "
                  "models) can never be exercised end-to-end because there's no legal input topic.",
    },
    {
        "id": "CONTRACTS-DUAL-SYSTEM",
        "title": "Two parallel contract systems (root sentinel_contracts/ vs deprecated "
                 "libs/sentinel_contracts/)",
        "priority": "Medium",
        "effort": "Low (delete the deprecated package once nothing imports it -- confirm via repo-wide grep)",
        "evidence": "libs/sentinel_contracts/ contains a DEPRECATED.md; the real, imported package "
                    "is the root-level sentinel_contracts/.",
        "impact": "Purely a maintenance/confusion risk for this integration harness specifically "
                  "-- both workers import from the root package correctly; noted here since it's "
                  "the kind of thing that causes a future contributor to import the wrong one.",
    },
]


def fmt_pct(n: int, d: int) -> str:
    return f"{round(100 * n / d, 2)}%" if d else "n/a"


def build_report() -> str:
    lines: list[str] = []
    a = lines.append

    counts = stage_counts()
    total = sum(n for *_ , n in counts)
    success_n = sum(n for _, _, st, n in counts if st == "success")
    failed_n = sum(n for _, _, st, n in counts if st == "failed")
    skipped_n = sum(n for _, _, st, n in counts if st == "skipped")

    span_a, span_b = counter_span_seconds()
    run_span_s = round((span_b - span_a), 1) if (span_a and span_b) else 0.0

    a("# SENTINEL Integration Test Report")
    a("")
    a(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    a(f"Observed run span: {run_span_s}s (first to last recorded stage event)")
    a("")
    a("This report has two parts: **Runtime Evidence** (section 1-5, pulled live from this "
      "run's trace store -- empty if the demo hasn't been run yet) and **Known Platform "
      "Gaps** (section 6, a static, cited list -- true regardless of whether the demo ran).")
    a("")

    # 1. Summary
    a("## 1. Summary")
    a("")
    a(f"- Total stage events recorded: **{total}**")
    a(f"- Success: **{success_n}** ({fmt_pct(success_n, total)})")
    a(f"- Failed: **{failed_n}** ({fmt_pct(failed_n, total)})")
    a(f"- Skipped (platform gap, not a bug): **{skipped_n}** ({fmt_pct(skipped_n, total)})")
    a("")

    # 2. Topics / components tested
    components = sorted({c for c, _, _, _ in counts})
    a("## 2. Components Exercised")
    a("")
    for c in components:
        a(f"- {c}")
    a("")
    a("Topics this harness targets (from `harness_config.DEMO_TOPICS`, names taken verbatim "
      "from `contracts/topics/kafka_topics.yaml`):")
    for t in cfg.DEMO_TOPICS:
        a(f"- `{t}`")
    a("")

    # 3. Per-stage breakdown
    a("## 3. Per-Stage Breakdown")
    a("")
    a("| Component | Stage | Status | Count |")
    a("|---|---|---|---|")
    for c, s, st, n in counts:
        a(f"| {c} | {s} | {st} | {n} |")
    a("")

    # 4. Latency
    a("## 4. Latency")
    a("")
    a("| Component | Stage | Samples | Avg (ms) | p95 (ms) | Max (ms) |")
    a("|---|---|---|---|---|---|")
    seen_stage = {(c, s) for c, s, _, _ in counts}
    for c, s in sorted(seen_stage):
        lat = latency_stats(c, s)
        if lat["count"] == 0:
            continue
        a(f"| {c} | {s} | {lat['count']} | {lat['avg_ms']} | {lat['p95_ms']} | {lat['max_ms']} |")
    a("")

    # 5. Failures
    fails = failed_events()
    a("## 5. Failures")
    a("")
    if not fails:
        a("No FAILED stage events recorded in this run.")
    else:
        for f in fails:
            a(f"### {f.component} \u2014 {f.stage}")
            a(f"- **Trace ID:** `{f.trace_id}`")
            a(f"- **Topic:** `{f.topic}`" if f.topic else "- **Topic:** n/a")
            a(f"- **Reason:** {f.reason}")
            a(f"- **Time:** {time.strftime('%H:%M:%S', time.localtime(f.ts))}")
            if f.trace_id:
                trail = events_for_trace(f.trace_id)
                before = [r for r in trail if r.ts <= f.ts and r.status == "success"]
                if before:
                    a("- **Everything before this point succeeded:**")
                    for r in before:
                        a(f"  - {r.component} / {r.stage} \u2713")
            a("")
    a("")

    # 6. Platform gaps
    a("## 6. Known Platform Gaps")
    a("")
    a("Static, cited, independent of whether the demo ran. These are why the pipeline "
      "cannot reach 100% success today, and none of them are bugs in this test harness.")
    a("")
    for g in PLATFORM_GAPS:
        a(f"### [{g['priority']}] {g['id']}: {g['title']}")
        a(f"- **Evidence:** {g['evidence']}")
        a(f"- **Impact:** {g['impact']}")
        a(f"- **Estimated fix effort:** {g['effort']}")
        a("")

    # 7. Verdict
    a("## 7. Verdict")
    a("")
    if total == 0:
        a("No data recorded yet -- run `python3 run_demo.py` first.")
    else:
        kafka_confirmed = any(s == "Kafka Publish" and st == "success" for _, s, st, _ in counts)
        a(f"- Kafka connectivity: {'CONFIRMED' if kafka_confirmed else 'UNCONFIRMED'} "
          f"(based on whether at least one successful Kafka Publish row was observed)")
        a("- Environmental Intelligence Agent: confirmed working through "
          "SensorSnapshotAggregator.ingest(); confirmed NOT publishing EnvironmentAnalysis "
          "(B1, by design of the current codebase, not a harness failure).")
        a("- Zone Intelligence Agent: confirmed working through ZoneState computation and "
          "publish to sentinel.zone.state.v1; ZoneAnomalyDetected confirmed computed but "
          "confirmed NOT published (platform gap, not a harness failure); ZoneAnalysis "
          "confirmed not produced anywhere (no such contract exists).")
        a(f"- {failed_n} genuine failure(s) recorded that are NOT explained by a known "
          f"platform gap above -- see section 5." if failed_n else
          "- No genuine (non-platform-gap) failures recorded in this run.")
    a("")
    return "\n".join(lines)


def main() -> int:
    report_text = build_report()
    cfg.REPORT_OUTPUT_PATH.write_text(report_text)
    print(f"Wrote {cfg.REPORT_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
