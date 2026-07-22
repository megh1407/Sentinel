"""
pipeline_visualizer.py

Live terminal monitor. Tails event_logger's SQLite store (polling for new
rows -- simple and correct across process boundaries; no message bus
needed for what is itself an observability tool) and renders each stage as
it's recorded, in the flow-diagram style the brief asked for:

  [Sensor Simulator] OK  SensorEvent Created           trace=a1b2c3...
    -> [Kafka] OK  Published  sentinel.sensor.events.v1
    -> [Environmental Agent] OK  SensorSnapshotAggregator Ingest (4.2ms)
    -> [Environmental Agent] -- Engine Services (skipped: B1/B3 gap)
    -> [Environmental Agent] -- EnvironmentAnalysis Publish (skipped: B1)

Usage:
    python3 pipeline_visualizer.py
    python3 pipeline_visualizer.py --since-start   # only show rows from process start onward
"""
from __future__ import annotations

import argparse
import sys
import time

from event_history import get_connection

COLOR = {
    "success": "\033[92m", "failed": "\033[91m", "skipped": "\033[93m", "info": "\033[94m",
}
RESET = "\033[0m"
MARK = {"success": "OK ", "failed": "FAIL", "skipped": "--  ", "info": "i   "}


def poll_new_rows(last_id: int):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM trace_events WHERE id > ? ORDER BY id ASC", (last_id,)).fetchall()
    finally:
        conn.close()
    return rows


def render_row(row) -> None:
    status = row["status"]
    color = COLOR.get(status, "")
    mark = MARK.get(status, "?")
    trace = (row["trace_id"] or "")[:12]
    loc = ""
    if row["topic"]:
        loc = f"  ({row['topic']}"
        if row["partition"] is not None:
            loc += f" p{row['partition']}"
        loc += ")"
    dur = f"  {row['duration_ms']:.1f}ms" if row["duration_ms"] is not None else ""
    print(f"{color}[{row['component']:<20s}] {mark}  {row['stage']}{dur}{loc}  trace={trace}{RESET}")
    if row["reason"]:
        print(f"    \u2514\u2500 {row['reason'][:160]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-start", action="store_true",
                         help="only show rows written after this monitor starts, not history")
    args = parser.parse_args()

    conn = get_connection()
    try:
        if args.since_start:
            last_id = conn.execute("SELECT COALESCE(MAX(id), 0) as m FROM trace_events").fetchone()["m"]
        else:
            last_id = 0
    finally:
        conn.close()

    print("Pipeline Visualizer -- tailing trace_events.db (Ctrl+C to stop)\n")
    try:
        while True:
            rows = poll_new_rows(last_id)
            for row in rows:
                render_row(row)
                last_id = row["id"]
            time.sleep(0.3)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
