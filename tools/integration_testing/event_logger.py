"""
event_logger.py

The one shared source of truth every other file in this harness reads from
or writes to. Simulators, agent workers, monitors, the dashboard, and the
failure report all run as SEPARATE processes (real Kafka is the only thing
connecting them -- no direct method calls, per the brief). They need a
place to record and reconstruct what happened that isn't Kafka itself
(Kafka doesn't remember "which stage a trace reached" as a queryable
concept). SQLite in WAL mode is used here rather than inventing a new
service: it's a single file, safe for multiple concurrent writers, needs no
extra infrastructure beyond the Python stdlib, and every column
below maps directly onto a field the brief explicitly asked to be traceable.

This file is NEVER imported by agent code -- only by harness scripts. It
does not modify, wrap, or monkeypatch anything in libs/sentinel_* or any
agent. Delete tools/integration_testing/ and nothing outside it changes.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

import harness_config as cfg

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    trace_id TEXT,
    correlation_id TEXT,
    event_id TEXT,
    component TEXT NOT NULL,       -- e.g. "Simulator", "Kafka", "Environmental Agent"
    stage TEXT NOT NULL,           -- e.g. "SensorEvent Created", "Published", "Received"
    topic TEXT,
    partition INTEGER,
    offset INTEGER,
    consumer_group TEXT,
    event_type TEXT,
    schema_version INTEGER,
    status TEXT NOT NULL,          -- "success" | "failed" | "skipped" | "info"
    reason TEXT,
    duration_ms REAL,
    extra_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_trace_id ON trace_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_ts ON trace_events(ts);
CREATE INDEX IF NOT EXISTS idx_component_stage ON trace_events(component, stage);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(cfg.TRACE_DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    """Wipes all recorded events -- used by run_demo.py at the start of a
    fresh demo run and by stop_demo.sh's optional cleanup, never by an
    agent or the simulators themselves."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM trace_events;")
        conn.commit()
    finally:
        conn.close()


@dataclass
class StageEvent:
    component: str
    stage: str
    status: str = "success"
    trace_id: str | None = None
    correlation_id: str | None = None
    event_id: str | None = None
    topic: str | None = None
    partition: int | None = None
    offset: int | None = None
    consumer_group: str | None = None
    event_type: str | None = None
    schema_version: int | None = None
    reason: str | None = None
    duration_ms: float | None = None
    extra: dict = field(default_factory=dict)


def log_stage(ev: StageEvent) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO trace_events (ts, trace_id, correlation_id, event_id, component, stage, "
            "topic, partition, offset, consumer_group, event_type, schema_version, status, reason, "
            "duration_ms, extra_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                time.time(), ev.trace_id, ev.correlation_id, ev.event_id, ev.component, ev.stage,
                ev.topic, ev.partition, ev.offset, ev.consumer_group, ev.event_type, ev.schema_version,
                ev.status, ev.reason, ev.duration_ms, json.dumps(ev.extra, default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def timed_stage(component: str, stage: str, trace_id: str | None = None, **kwargs):
    """`with timed_stage("Environmental Agent", "ThresholdService") as ev: ...`
    Logs one SUCCESS row on clean exit (duration_ms filled in automatically),
    or one FAILED row (with the exception's type/message as `reason`) if the
    block raises -- and re-raises, since a testing harness must never
    swallow the very failures it exists to surface."""
    start = time.time()
    ev = StageEvent(component=component, stage=stage, trace_id=trace_id, **kwargs)
    try:
        yield ev
        ev.duration_ms = (time.time() - start) * 1000
        log_stage(ev)
    except Exception as e:  # noqa: BLE001 -- deliberate: record then propagate
        ev.status = "failed"
        ev.reason = f"{type(e).__name__}: {e}"
        ev.duration_ms = (time.time() - start) * 1000
        log_stage(ev)
        raise


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


init_db()
