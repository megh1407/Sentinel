"""
event_history.py

Read-only query helpers over event_logger's SQLite store. Used by
trace_dashboard.py, pipeline_visualizer.py, and failure_report.py so none
of them duplicate SQL. Nothing here writes to the store.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from event_logger import get_connection


@dataclass
class Row:
    id: int
    ts: float
    trace_id: str | None
    correlation_id: str | None
    event_id: str | None
    component: str
    stage: str
    topic: str | None
    partition: int | None
    offset: int | None
    consumer_group: str | None
    event_type: str | None
    schema_version: int | None
    status: str
    reason: str | None
    duration_ms: float | None
    extra: dict

    @classmethod
    def from_sqlite(cls, r) -> "Row":
        return cls(
            id=r["id"], ts=r["ts"], trace_id=r["trace_id"], correlation_id=r["correlation_id"],
            event_id=r["event_id"], component=r["component"], stage=r["stage"], topic=r["topic"],
            partition=r["partition"], offset=r["offset"], consumer_group=r["consumer_group"],
            event_type=r["event_type"], schema_version=r["schema_version"], status=r["status"],
            reason=r["reason"], duration_ms=r["duration_ms"],
            extra=json.loads(r["extra_json"]) if r["extra_json"] else {},
        )


def all_trace_ids(limit: int = 500) -> list[str]:
    """Bare trace_id list, most-recently-started first. Kept for backward
    compatibility with anything that only wants the IDs; trace_summaries()
    below is what trace_dashboard.py --list actually renders."""
    return [s.trace_id for s in trace_summaries(limit=limit)]


@dataclass
class TraceSummary:
    trace_id: str
    first_ts: float
    last_ts: float
    event_count: int
    components: list[str]
    has_failure: bool


def trace_summaries(limit: int = 500) -> list[TraceSummary]:
    """One row per trace_id with real aggregates. The original bug here
    was `SELECT DISTINCT trace_id ... ORDER BY MIN(ts)` -- SQLite (correctly)
    rejects an aggregate function in ORDER BY against a plain SELECT DISTINCT
    with no GROUP BY ("misuse of aggregate: MIN()"). Fixed by grouping
    explicitly, which is also what actually lets us report first/last
    timestamp and event count per trace, not just an ID."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT trace_id, MIN(ts) as first_ts, MAX(ts) as last_ts, COUNT(*) as n, "
            "GROUP_CONCAT(DISTINCT component) as components, "
            "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as n_failed "
            "FROM trace_events WHERE trace_id IS NOT NULL "
            "GROUP BY trace_id ORDER BY first_ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        TraceSummary(
            trace_id=r["trace_id"], first_ts=r["first_ts"], last_ts=r["last_ts"], event_count=r["n"],
            components=(r["components"] or "").split(","), has_failure=bool(r["n_failed"]),
        )
        for r in rows
    ]


@dataclass
class RunWindow:
    run_index: int
    start_ts: float
    end_ts: float
    event_count: int
    trace_count: int


def detect_runs(gap_seconds: float = 30.0) -> list[RunWindow]:
    """Groups ALL rows in the store into "runs" by time-gap-based session
    boundaries: whenever the time between one row and the next exceeds
    `gap_seconds`, a new run starts. This exists because there is no
    single trace_id spanning an entire integration-test run (each
    SensorEvent/WorkerEvent/PermitEvent gets its own trace_id derived from
    its own correlation_id) -- a "run" is a time window containing many
    independent traces, not one trace. In the common case (event_logger.
    reset_db() wipes the store at the start of every run_demo.py
    invocation) this returns exactly one run; multiple runs only appear if
    the store wasn't reset between separate invocations."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT ts, trace_id FROM trace_events ORDER BY ts ASC").fetchall()
    finally:
        conn.close()
    if not rows:
        return []

    runs: list[RunWindow] = []
    run_start = rows[0]["ts"]
    prev_ts = rows[0]["ts"]
    count = 1
    trace_ids: set = {rows[0]["trace_id"]} if rows[0]["trace_id"] else set()
    run_index = 0

    def _flush(end_ts: float):
        nonlocal run_index
        runs.append(RunWindow(run_index=run_index, start_ts=run_start, end_ts=end_ts,
                               event_count=count, trace_count=len(trace_ids)))
        run_index += 1

    for r in rows[1:]:
        if r["ts"] - prev_ts > gap_seconds:
            _flush(prev_ts)
            run_start = r["ts"]
            count = 0
            trace_ids = set()
        count += 1
        if r["trace_id"]:
            trace_ids.add(r["trace_id"])
        prev_ts = r["ts"]
    _flush(prev_ts)
    return runs


def events_in_window(start_ts: float, end_ts: float) -> list[Row]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trace_events WHERE ts >= ? AND ts <= ? ORDER BY ts ASC", (start_ts, end_ts)
        ).fetchall()
    finally:
        conn.close()
    return [Row.from_sqlite(r) for r in rows]


def events_for_trace(trace_id: str) -> list[Row]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trace_events WHERE trace_id = ? ORDER BY ts ASC", (trace_id,)
        ).fetchall()
    finally:
        conn.close()
    return [Row.from_sqlite(r) for r in rows]


def recent_events(limit: int = 200, component: str | None = None) -> list[Row]:
    conn = get_connection()
    try:
        if component:
            rows = conn.execute(
                "SELECT * FROM trace_events WHERE component = ? ORDER BY ts DESC LIMIT ?",
                (component, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trace_events ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
    finally:
        conn.close()
    return [Row.from_sqlite(r) for r in rows][::-1]


def failed_events(since_ts: float | None = None) -> list[Row]:
    conn = get_connection()
    try:
        if since_ts is not None:
            rows = conn.execute(
                "SELECT * FROM trace_events WHERE status = 'failed' AND ts >= ? ORDER BY ts ASC", (since_ts,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM trace_events WHERE status = 'failed' ORDER BY ts ASC").fetchall()
    finally:
        conn.close()
    return [Row.from_sqlite(r) for r in rows]


def stage_counts(since_ts: float | None = None) -> list[tuple[str, str, str, int]]:
    """Returns (component, stage, status, count) tuples -- the shape the
    validation report's per-stage breakdown and the live dashboard's
    summary panel both need."""
    conn = get_connection()
    try:
        if since_ts is not None:
            rows = conn.execute(
                "SELECT component, stage, status, COUNT(*) as n FROM trace_events WHERE ts >= ? "
                "GROUP BY component, stage, status ORDER BY component, stage", (since_ts,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT component, stage, status, COUNT(*) as n FROM trace_events "
                "GROUP BY component, stage, status ORDER BY component, stage"
            ).fetchall()
    finally:
        conn.close()
    return [(r["component"], r["stage"], r["status"], r["n"]) for r in rows]


def latency_stats(component: str, stage: str, since_ts: float | None = None) -> dict:
    conn = get_connection()
    try:
        query = "SELECT duration_ms FROM trace_events WHERE component=? AND stage=? AND duration_ms IS NOT NULL"
        params: list = [component, stage]
        if since_ts is not None:
            query += " AND ts >= ?"
            params.append(since_ts)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    values = sorted(r["duration_ms"] for r in rows)
    if not values:
        return {"count": 0, "avg_ms": None, "p95_ms": None, "max_ms": None}
    p95_idx = min(len(values) - 1, int(len(values) * 0.95))
    return {
        "count": len(values),
        "avg_ms": round(sum(values) / len(values), 2),
        "p95_ms": round(values[p95_idx], 2),
        "max_ms": round(values[-1], 2),
    }


def counter_span_seconds() -> tuple[float | None, float | None]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT MIN(ts) as a, MAX(ts) as b FROM trace_events").fetchone()
    finally:
        conn.close()
    return (row["a"], row["b"])
