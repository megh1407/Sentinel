"""
latency_monitor.py

Throughput and latency metrics from the trace store: events/sec (derived
from stage rows), per-stage avg/p95 duration, and end-to-end span per
trace (first row timestamp to last row timestamp, across every component
that trace touched).

Usage:
    python3 latency_monitor.py
    python3 latency_monitor.py --watch 5
"""
from __future__ import annotations

import argparse
import sys
import time

from event_history import get_connection, latency_stats, stage_counts

TRACKED_STAGES = [
    ("Sensor Simulator", "SensorEvent Created"),
    ("Worker Simulator", "WorkerEvent Created"),
    ("Permit Simulator", "PermitEvent Created"),
    ("Environmental Agent", "SensorSnapshotAggregator Ingest"),
    ("Zone Agent", "ZoneState Computed"),
]


def events_per_second(component: str, stage: str, window_seconds: float = 30.0) -> float:
    conn = get_connection()
    try:
        since = time.time() - window_seconds
        row = conn.execute(
            "SELECT COUNT(*) as n, MIN(ts) as a, MAX(ts) as b FROM trace_events "
            "WHERE component=? AND stage=? AND status='success' AND ts >= ?",
            (component, stage, since),
        ).fetchone()
    finally:
        conn.close()
    if not row or row["n"] == 0:
        return 0.0
    span = max(1e-6, (row["b"] - row["a"])) if row["n"] > 1 else window_seconds
    return round(row["n"] / span, 3)


def end_to_end_trace_spans() -> dict:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT trace_id, MIN(ts) as a, MAX(ts) as b, COUNT(*) as n "
            "FROM trace_events WHERE trace_id IS NOT NULL GROUP BY trace_id"
        ).fetchall()
    finally:
        conn.close()
    spans_ms = [(r["b"] - r["a"]) * 1000 for r in rows if r["n"] > 1]
    if not spans_ms:
        return {"count": 0, "avg_ms": None, "p95_ms": None, "max_ms": None}
    spans_ms.sort()
    p95_idx = min(len(spans_ms) - 1, int(len(spans_ms) * 0.95))
    return {
        "count": len(spans_ms),
        "avg_ms": round(sum(spans_ms) / len(spans_ms), 2),
        "p95_ms": round(spans_ms[p95_idx], 2),
        "max_ms": round(spans_ms[-1], 2),
    }


def report() -> None:
    print(f"\n{'=' * 70}\nLatency / Throughput Monitor -- {time.strftime('%H:%M:%S')}\n{'=' * 70}")

    print(f"\n{'Stage':<55s} {'events/sec (30s)':<18s}")
    for component, stage in TRACKED_STAGES:
        eps = events_per_second(component, stage)
        print(f"{component + ' > ' + stage:<55s} {eps:<18.3f}")

    print(f"\n{'Stage':<55s} {'count':<7s} {'avg ms':<9s} {'p95 ms':<9s} {'max ms':<9s}")
    for component, stage in TRACKED_STAGES:
        s = latency_stats(component, stage)
        print(f"{component + ' > ' + stage:<55s} {s['count']:<7d} "
              f"{str(s['avg_ms']):<9s} {str(s['p95_ms']):<9s} {str(s['max_ms']):<9s}")

    e2e = end_to_end_trace_spans()
    print("\nEnd-to-end trace span (first row -> last row observed for that trace_id):")
    print(f"  traces measured: {e2e['count']}   avg: {e2e['avg_ms']} ms   "
          f"p95: {e2e['p95_ms']} ms   max: {e2e['max_ms']} ms")

    failed = sum(n for _, _, st, n in stage_counts() if st == "failed")
    total = sum(n for _, _, _, n in stage_counts())
    rate = round(100 * failed / total, 2) if total else 0.0
    print(f"\nOverall failure rate across all logged stages: {failed}/{total} ({rate}%)\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", type=float, default=None)
    args = parser.parse_args()

    if args.watch is None:
        report()
        return 0
    try:
        while True:
            report()
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
