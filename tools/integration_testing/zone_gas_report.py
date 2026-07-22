"""
zone_gas_report.py

Generates zone_environmental_integration_report.md from real evidence in
event_logger's trace store for one run (a time window -- see
event_history.detect_runs()). Every number in the generated report is a
real query result over that window; nothing is inferred, assumed, or
filled in from what "should" have happened. Where the trace store has no
row to answer a question, the report says NO_TRACE_EVIDENCE / UNKNOWN
rather than guessing.

Two kinds of "no" are deliberately kept separate throughout, per the
brief's Part 7:

  - PLATFORM_GAP: something structurally cannot happen in the CURRENT
    CODE, independent of this run's data (e.g. Environmental Agent can
    never publish EnvironmentAnalysis -- confirmed by reading main.py's
    RuntimeError, not by an absence of trace rows). These are asserted
    with a citation, not a query.
  - OBSERVABILITY_GAP / NO_TRACE_EVIDENCE: the trace store simply has no
    row either way -- this does NOT mean "it didn't happen," it means
    "this run's tracing can't tell you." Reported as such, not as failure.

Invoked via: python3 trace_dashboard.py --report <run_index|latest>
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import harness_config as cfg
from event_history import Row, RunWindow, events_in_window

SENSOR_COMPONENTS = {"Sensor Simulator", "Sensor Simulator (Data Engine)"}
WORKER_COMPONENTS = {"Worker Simulator", "Worker Simulator (Data Engine)"}
PERMIT_COMPONENTS = {"Permit Simulator", "Permit Simulator (Data Engine)"}
ENV_AGENT = "Environmental Agent"
ZONE_AGENT = "Zone Agent"

GAS_SENSOR_TYPES = {"GAS"}  # real SensorType enum value for gas readings

ENGINE_SERVICES_STAGE = "Engine Services (Threshold/Trend/Prediction/Correlation/Risk/Recommendation/...)"
ENV_ANALYSIS_PUBLISH_STAGE = "EnvironmentAnalysis Publish"


def _match(r: Row, components=None, stage=None, status=None, topic=None) -> bool:
    if components is not None and r.component not in components:
        return False
    if stage is not None and r.stage != stage:
        return False
    if status is not None and r.status != status:
        return False
    if topic is not None and r.topic != topic:
        return False
    return True


def _filter(rows: list[Row], **kw) -> list[Row]:
    return [r for r in rows if _match(r, **kw)]


def _fmt_ts(ts: float | None) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts)) if ts is not None else "N/A"


def _evidence_line(rows: list[Row], label: str) -> str:
    if not rows:
        return f"NO_TRACE_EVIDENCE -- no `{label}` rows in this run's window."
    first, last = rows[0].ts, rows[-1].ts
    return f"{len(rows)} `{label}` row(s), {_fmt_ts(first)} \u2192 {_fmt_ts(last)}."


def _yn(rows: list[Row], label: str) -> tuple[str, str]:
    if rows:
        return "YES", _evidence_line(rows, label)
    return "NO", _evidence_line(rows, label)


def generate_report_for_run(run: RunWindow, output_path: str | None = None) -> str:
    rows = events_in_window(run.start_ts, run.end_ts)
    lines: list[str] = []
    a = lines.append

    # --- Part A data pulls -------------------------------------------------
    sensor_created = [r for r in _filter(rows, components=SENSOR_COMPONENTS, status="success")
                       if "SensorEvent" in r.stage and "Created" in r.stage]
    sensor_published = _filter(rows, components=SENSOR_COMPONENTS, stage="Kafka Publish", status="success")
    sensor_publish_failed = _filter(rows, components=SENSOR_COMPONENTS, stage="Kafka Publish", status="failed")

    worker_created = [r for r in _filter(rows, components=WORKER_COMPONENTS, status="success")
                       if "WorkerEvent" in r.stage and "Created" in r.stage]
    worker_published = _filter(rows, components=WORKER_COMPONENTS, stage="Kafka Publish", status="success")

    permit_created = [r for r in _filter(rows, components=PERMIT_COMPONENTS, status="success")
                       if "PermitEvent" in r.stage and "Created" in r.stage]
    permit_published = _filter(rows, components=PERMIT_COMPONENTS, stage="Kafka Publish", status="success")

    env_subscribed = _filter(rows, components={ENV_AGENT}, stage="Kafka Subscribe", status="success")
    env_received = _filter(rows, components={ENV_AGENT}, stage="Kafka Message Received", status="success")
    env_processed = _filter(rows, components={ENV_AGENT}, stage="SensorSnapshotAggregator Ingest", status="success")
    env_engine_services = _filter(rows, components={ENV_AGENT}, stage=ENGINE_SERVICES_STAGE)
    env_analysis_publish = _filter(rows, components={ENV_AGENT}, stage=ENV_ANALYSIS_PUBLISH_STAGE)

    zone_subscribed = _filter(rows, components={ZONE_AGENT}, stage="Kafka Subscribe", status="success")
    zone_received = _filter(rows, components={ZONE_AGENT}, stage="Kafka Message Received", status="success")
    zone_state_computed = _filter(rows, components={ZONE_AGENT}, stage="ZoneState Computed", status="success")
    zone_state_published = _filter(rows, components={ZONE_AGENT}, stage="Kafka Publish", status="success",
                                    topic=cfg.TOPIC_ZONE_STATE)
    zone_state_publish_failed = _filter(rows, components={ZONE_AGENT}, stage="Kafka Publish", status="failed",
                                         topic=cfg.TOPIC_ZONE_STATE)
    zone_anomaly_computed = _filter(rows, components={ZONE_AGENT},
                                     stage="ZoneAnomalyDetected Computed (not published)")

    # gas-specific breakdown from sensor "Created" rows' extra JSON
    sensor_type_counts: dict[str, int] = {}
    gas_readings = []
    for r in sensor_created:
        st = r.extra.get("sensor_type")
        if st:
            sensor_type_counts[st] = sensor_type_counts.get(st, 0) + 1
            if st in GAS_SENSOR_TYPES:
                gas_readings.append(r)

    failures = [r for r in rows if r.status == "failed"]

    # --- Executive verdict ---------------------------------------------
    sensor_ok = bool(sensor_published)
    env_received_ok = bool(env_received)
    env_produced_result = bool(env_analysis_publish) and any(r.status == "success" for r in env_analysis_publish)
    zone_input_ok = bool(zone_received)
    zone_output_ok = bool(zone_state_published)

    if failures and not env_produced_result:
        # genuine runtime failures on top of the known platform gap
        verdict = "PARTIALLY VERIFIED" if (sensor_ok and zone_output_ok) else "FAILED AT RUNTIME"
    elif sensor_ok and env_received_ok and zone_input_ok and zone_output_ok and not env_produced_result:
        verdict = "PARTIALLY VERIFIED -- BLOCKED BY PLATFORM GAP (B1)"
    elif sensor_ok and zone_output_ok:
        verdict = "PARTIALLY VERIFIED"
    else:
        verdict = "FAILED AT RUNTIME" if rows else "NO DATA"

    # ==================================================================
    a("# Zone + Environmental/Gas Real Integration Test Report")
    a("")
    a(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    a("")
    a("## 1. Test Identity")
    a("")
    a(f"- Run index: {run.run_index}")
    a(f"- Start time: {_fmt_ts(run.start_ts)}")
    a(f"- End time: {_fmt_ts(run.end_ts)}")
    a(f"- Duration: {round(run.end_ts - run.start_ts, 1)}s")
    a(f"- Total stage events in window: {run.event_count}")
    a(f"- Distinct traces in window: {run.trace_count}")
    a(f"- Kafka broker: `{cfg.KAFKA_BOOTSTRAP_SERVERS}`")
    a(f"- Trace store: `{cfg.TRACE_DB_PATH}`")
    a("")
    a("Note on identity: this run is identified by a TIME WINDOW, not a single trace_id. "
      "Each SensorEvent/WorkerEvent/PermitEvent gets its own trace_id (derived from its own "
      "correlation_id) -- there is no trace_id that spans an entire test run in this schema. "
      "See `event_history.detect_runs()`'s docstring.")
    a("")

    a("## 2. Executive Verdict")
    a("")
    a(f"**{verdict}**")
    a("")
    a("\"Success\" is never claimed here unless the full chain "
      "(input generated -> Kafka published -> agent consumed -> agent processed -> output "
      "generated -> output published -> downstream agent consumed) is proven by trace rows below.")
    a("")

    a("## 3. Actual Pipeline")
    a("")
    def mark(ok: bool | None, gap: bool = False) -> str:
        if gap:
            return "\U0001F6A7 PLATFORM GAP"
        if ok is None:
            return "\u26A0 NO EVIDENCE"
        return "\u2705 VERIFIED" if ok else "\u274C FAILED"

    a("```")
    a("Sensor Simulator")
    a(f"    | {mark(sensor_ok)}  ({len(sensor_created)} created, {len(sensor_published)} published)")
    a("    v")
    a("Kafka (sentinel.sensor.events.v1)")
    a("    v")
    a("Environmental Agent")
    a(f"    | {mark(env_received_ok)}  ({len(env_received)} Kafka Message Received rows)")
    a("    v")
    a("Gas / Environmental Processing (Threshold/Trend/Prediction/Risk/Recommendation)")
    a(f"    | {mark(None, gap=True)}  constructed in initialize(), never called from process() -- see Part 4")
    a("    v")
    a("EnvironmentAnalysis result")
    a(f"    | {mark(None, gap=True)}  no generated model exists for this contract (B1)")
    a("    v")
    a("Zone Agent (environmental input)")
    a(f"    | {mark(None, gap=True)}  Zone Agent's INPUT_TOPICS never included the environmental-analysis "
      f"topic in the first place -- see Part 5C")
    a("")
    a("Worker/Permit Simulators")
    a(f"    | {mark(bool(worker_published) or bool(permit_published))}  "
      f"({len(worker_published)} worker + {len(permit_published)} permit published)")
    a("    v")
    a("Zone Agent")
    a(f"    | {mark(zone_input_ok)}  ({len(zone_received)} Kafka Message Received rows)")
    a("    v")
    a("ZoneState computation")
    a(f"    | {mark(bool(zone_state_computed))}  ({len(zone_state_computed)} computed)")
    a("    v")
    a("Kafka (sentinel.zone.state.v1)")
    a(f"    | {mark(zone_output_ok)}  ({len(zone_state_published)} published, "
      f"{len(zone_state_publish_failed)} failed)")
    a("```")
    a("")

    # --- Part 4 event count table ---------------------------------------
    a("## 4. Event Counts")
    a("")
    a("| Event | Created | Published | Consumed (received) | Processed | Output |")
    a("|---|---:|---:|---:|---:|---:|")
    a(f"| SensorEvent | {len(sensor_created)} | {len(sensor_published)} | {len(env_received)} "
      f"| {len(env_processed)} | 0 (B1 -- see Part 9) |")
    a(f"| WorkerEvent | {len(worker_created)} | {len(worker_published)} | "
      f"{len(_filter(rows, components={ZONE_AGENT}, stage='Kafka Message Received', status='success', topic=cfg.TOPIC_WORKER_EVENTS))} "
      f"| UNKNOWN (no per-event-type processed stage logged) | N/A |")
    a(f"| PermitEvent | {len(permit_created)} | {len(permit_published)} | "
      f"{len(_filter(rows, components={ZONE_AGENT}, stage='Kafka Message Received', status='success', topic=cfg.TOPIC_PERMIT_EVENTS))} "
      f"| UNKNOWN (no per-event-type processed stage logged) | N/A |")
    a(f"| Environmental result | 0 | 0 | N/A | N/A | 0 (PLATFORM_GAP: B1) |")
    a(f"| ZoneState | {len(zone_state_computed)} | {len(zone_state_published)} | N/A | N/A | "
      f"{len(zone_state_published)} |")
    a("")

    # --- Part 4 gas breakdown --------------------------------------------
    a("## 5. Environmental/Gas Agent Evidence")
    a("")
    a(f"- Sensor events received by Environmental Agent: **{len(env_received)}**")
    a(f"- SensorSnapshotAggregator.ingest() executed (success): **{len(env_processed)}**")
    a(f"- Sensor type distribution (from real event payloads this run): "
      f"{json.dumps(sensor_type_counts) if sensor_type_counts else 'NO_TRACE_EVIDENCE'}")
    a(f"- Gas-specific (`sensor_type=GAS`) readings observed: **{len(gas_readings)}**")
    a("")
    a("| Stage | Status | Evidence |")
    a("|---|---|---|")
    a(f"| ThresholdService | NOT_EXECUTED | Constructed in `initialize()`, never invoked by `process()` -- "
      f"confirmed by reading `environmental_intelligence_agent.py`, not by absence of trace rows. |")
    a(f"| TrendService | NOT_EXECUTED | same as above |")
    a(f"| PredictionService | NOT_EXECUTED | same as above |")
    a(f"| CorrelationService | NOT_EXECUTED | same as above |")
    a(f"| RiskService | NOT_EXECUTED | same as above |")
    a(f"| RecommendationService | NOT_EXECUTED | same as above |")
    a(f"| EnvironmentAnalysis publish | PLATFORM_GAP | {len(env_engine_services)} `{ENGINE_SERVICES_STAGE}` "
      f"skipped-row(s) and {len(env_analysis_publish)} `{ENV_ANALYSIS_PUBLISH_STAGE}` skipped-row(s) recorded "
      f"this run, each citing B1 (no generated model for sentinel.environment.analysis.v1). |")
    a("")
    a("This is asserted as PLATFORM_GAP, not derived solely from this run's trace rows -- the skipped-row "
      "counts above are corroborating evidence that the code behaved exactly as its own source says it will, "
      "not the primary proof (the primary proof is the RuntimeError in "
      "`agents/environmental-intelligence-agent/main.py` and the repo-wide absence of an `EnvironmentAnalysis` class).")
    a("")

    a("## 6. Zone Agent Evidence")
    a("")
    a(f"- Worker events received: **{len(_filter(rows, components={ZONE_AGENT}, stage='Kafka Message Received', status='success', topic=cfg.TOPIC_WORKER_EVENTS))}**")
    a(f"- Permit events received: **{len(_filter(rows, components={ZONE_AGENT}, stage='Kafka Message Received', status='success', topic=cfg.TOPIC_PERMIT_EVENTS))}**")
    a(f"- Environmental/gas-derived events received: **0** -- PLATFORM_GAP, see Part 9. Zone Agent's "
      f"`INPUT_TOPICS` never included an environmental-analysis topic to begin with.")
    a(f"- ZoneState computations: **{len(zone_state_computed)}**")
    a(f"- ZoneState publications (success): **{len(zone_state_published)}**  (failed: {len(zone_state_publish_failed)})")
    a(f"- ZoneAnomalyDetected computed internally: **{len(zone_anomaly_computed)}**")
    a(f"- ZoneAnomalyDetected published to Kafka: **0** -- PLATFORM_GAP, no registered output topic "
      f"(`main.py`'s `_ZoneAnomalySuppressingAgent` strips it before publish).")
    a("")

    # --- Part 7 Q&A -------------------------------------------------------
    a("## 7. End-to-End Correlation")
    a("")

    q1_ans, q1_ev = _yn(sensor_published, "Kafka Publish (sensor)")
    a("### Question 1: Did a real sensor/gas event enter Kafka?")
    a(f"```\n{q1_ans}\n```")
    a(f"Evidence: {q1_ev}")
    a("")

    q2_ans, q2_ev = _yn(env_received, "Kafka Message Received (Environmental Agent)")
    a("### Question 2: Did the Environmental Agent receive it?")
    a(f"```\n{q2_ans}\n```")
    a(f"Evidence: {q2_ev}")
    a("")

    a("### Question 3: Did gas processing execute?")
    a("```\nNO\n```")
    a("Evidence: PLATFORM_GAP, not run-dependent -- `environmental_intelligence_agent.py`'s `process()` "
      f"calls only `SensorSnapshotAggregator.ingest()` ({len(env_processed)} times this run) and returns. "
      f"ThresholdService/TrendService/PredictionService/CorrelationService/RiskService/RecommendationService "
      "are constructed in `initialize()` but never invoked. This is true of the code regardless of what "
      "this run's trace shows.")
    a("")

    a("### Question 4: Did the resulting environmental information reach Zone Agent?")
    a("```\nNO\n```")
    a("Evidence: PLATFORM_GAP -- there is no environmental result to reach anything (see Question 3), and "
      "independently, Zone Intelligence Agent's own `INPUT_TOPICS` "
      "(`sentinel.sensor.events.v1`, `sentinel.worker.events.v1`, `sentinel.permit.events.v1`) never "
      "included an environmental-analysis topic at all -- confirmed by reading "
      "`agents/zone_intelligence_agent/main.py`.")
    a("")

    q5_ans, q5_ev = _yn(zone_state_computed, "ZoneState Computed")
    a("### Question 5: Did Zone Agent compute ZoneState from real inputs?")
    a(f"```\n{q5_ans}\n```")
    a(f"Evidence: {q5_ev} Real inputs this run: {len(worker_published)} WorkerEvent + "
      f"{len(permit_published)} PermitEvent published, "
      f"{len(_filter(rows, components={ZONE_AGENT}, stage='Kafka Message Received', status='success'))} "
      f"total Kafka Message Received rows at Zone Agent.")
    a("")

    q6_ans, q6_ev = _yn(zone_state_published, "Kafka Publish (ZoneState)")
    a("### Question 6: Was ZoneState published to Kafka?")
    a(f"```\n{q6_ans}\n```")
    a(f"Evidence: {q6_ev}")
    a("")

    # --- Part 9 platform gaps (static, always present) --------------------
    a("## 8. Known Platform Gaps (Not Hidden)")
    a("")
    a("- **B1 -- EnvironmentAnalysis**: no generated Pydantic model for `sentinel.environment.analysis.v1` "
      "anywhere in the repo. Environmental Intelligence Agent's `main.py` refuses to start via `AgentRunner` "
      "over this exact gap. Classification: `PLATFORM_GAP`.")
    a("- **ZoneAnalysis**: `sentinel.zone.analysis.v1` has no generated model and is never wired anywhere. "
      "`ZoneState != ZoneAnalysis` -- they are different, unrelated outputs; this report does not conflate "
      "them. Classification: `PLATFORM_GAP`.")
    a("- **ZoneAnomalyDetected**: computed internally (with Postgres audit rows, per that class's own "
      "docstring) but never published to Kafka -- no registered output topic exists for it. "
      "Status: `COMPUTED INTERNALLY, NOT PUBLISHED TO KAFKA`. Not reported as end-to-end successful anywhere "
      "in this report.")
    a("")

    # --- Failures -----------------------------------------------------
    a("## 9. Genuine Runtime Failures (excluding known platform gaps)")
    a("")
    if not failures:
        a("None recorded in this run's window.")
    else:
        for f in failures:
            a(f"- **{f.component} / {f.stage}** at {_fmt_ts(f.ts)} -- {f.reason} "
              f"(trace_id=`{f.trace_id}`) -- Classification: `RUNTIME_FAILURE`")
    a("")

    a("## 10. Reproducibility")
    a("")
    a("```")
    a(f"python3 trace_dashboard.py --list-runs")
    a(f"python3 trace_dashboard.py --report {run.run_index}")
    a("```")
    a("")

    text = "\n".join(lines)
    out_path = Path(output_path) if output_path else (cfg.HARNESS_DIR / "zone_environmental_integration_report.md")
    out_path.write_text(text)
    return str(out_path)
