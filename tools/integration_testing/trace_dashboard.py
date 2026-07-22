"""
trace_dashboard.py

Reconstructs one trace's complete path from event_logger's store and
prints it as a timeline (stage name, elapsed time from the trace's first
row, status). Also lists recent traces and detected "runs" (time-window
groupings -- see event_history.detect_runs()'s docstring for why a run
isn't the same thing as a trace_id in this schema).

Usage:
    python3 trace_dashboard.py <trace_id>
    python3 trace_dashboard.py --latest              # most recently started trace
    python3 trace_dashboard.py --list                 # table of recent trace ids
    python3 trace_dashboard.py --list-runs             # detected run time-windows
    python3 trace_dashboard.py --report latest          # generate zone_environmental_integration_report.md for the latest run
    python3 trace_dashboard.py --report 0 --output out.md
"""
from __future__ import annotations

import argparse
import sys
import time

from event_history import all_trace_ids, detect_runs, events_for_trace, trace_summaries

STATUS_MARK = {"success": "\033[92m\u2713\033[0m", "failed": "\033[91m\u2717\033[0m",
               "skipped": "\033[93m\u2013\033[0m", "info": "\033[94mi\033[0m"}


def render(trace_id: str) -> bool:
    rows = events_for_trace(trace_id)
    if not rows:
        print(f"No events recorded for trace_id={trace_id}")
        return False

    t0 = rows[0].ts
    print(f"\nTrace ID: {trace_id}")
    print(f"{len(rows)} stage(s), first seen {rows[0].component}/{rows[0].stage}\n")
    overall_ok = True
    for r in rows:
        mark = STATUS_MARK.get(r.status, "?")
        elapsed_ms = (r.ts - t0) * 1000
        dur = f" ({r.duration_ms:.1f}ms)" if r.duration_ms is not None else ""
        loc = ""
        if r.topic:
            loc = f"  [{r.topic}"
            if r.partition is not None:
                loc += f" p{r.partition}"
            if r.offset is not None:
                loc += f"@{r.offset}"
            loc += "]"
        print(f"  {elapsed_ms:8.1f}ms  {mark}  {r.component:<20s} {r.stage}{dur}{loc}")
        if r.reason:
            print(f"              \u2514\u2500 {r.reason}")
        if r.status == "failed":
            overall_ok = False

    total_ms = (rows[-1].ts - t0) * 1000
    print(f"\n  Total observed span: {total_ms:.1f}ms")
    print(f"  Result: {'SUCCESS' if overall_ok else 'FAILED'}\n")
    return overall_ok


def print_list() -> None:
    summaries = trace_summaries(limit=200)
    print(f"{len(summaries)} recent trace(s) (most recently started first):\n")
    print(f"{'TRACE ID':<38s} {'FIRST EVENT':<12s} {'LAST EVENT':<12s} {'EVENTS':>7s}  COMPONENTS")
    print("-" * 100)
    for s in summaries:
        first_str = time.strftime("%H:%M:%S", time.localtime(s.first_ts))
        last_str = time.strftime("%H:%M:%S", time.localtime(s.last_ts))
        flag = " (has failure)" if s.has_failure else ""
        print(f"{s.trace_id:<38s} {first_str:<12s} {last_str:<12s} {s.event_count:>7d}  "
              f"{','.join(c for c in s.components if c)}{flag}")
    print("\nNote: each trace_id here is ONE event's path (one SensorEvent/WorkerEvent/"
          "PermitEvent), not an entire test run -- a full run is made of many traces. "
          "Use --list-runs to see run-level time windows and total event counts.")


def print_list_runs() -> None:
    runs = detect_runs()
    if not runs:
        print("No runs detected -- trace store is empty.")
        return
    print(f"{len(runs)} run(s) detected (gap-based session grouping, 30s threshold):\n")
    print(f"{'RUN':>4s} {'START':<12s} {'END':<12s} {'DURATION':>10s} {'EVENTS':>8s} {'TRACES':>8s}")
    print("-" * 62)
    for r in runs:
        start_str = time.strftime("%H:%M:%S", time.localtime(r.start_ts))
        end_str = time.strftime("%H:%M:%S", time.localtime(r.end_ts))
        dur = f"{r.end_ts - r.start_ts:.1f}s"
        print(f"{r.run_index:>4d} {start_str:<12s} {end_str:<12s} {dur:>10s} {r.event_count:>8d} {r.trace_count:>8d}")


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("trace_id", nargs="?", default=None)
    group.add_argument("--latest", action="store_true")
    group.add_argument("--list", action="store_true")
    group.add_argument("--list-runs", action="store_true")
    group.add_argument("--report", metavar="RUN_INDEX|latest", default=None,
                        help="generate zone_environmental_integration_report.md for a run "
                             "(run index from --list-runs, or 'latest')")
    parser.add_argument("--output", default=None, help="output path for --report (default: "
                                                         "zone_environmental_integration_report.md)")
    parser.add_argument("--gap-seconds", type=float, default=30.0,
                         help="run-boundary gap threshold in seconds (used by --list-runs / --report)")
    args = parser.parse_args()

    if args.list:
        print_list()
        return 0

    if args.list_runs:
        print_list_runs()
        return 0

    if args.report is not None:
        from zone_gas_report import generate_report_for_run
        runs = detect_runs(gap_seconds=args.gap_seconds)
        if not runs:
            print("No runs detected -- trace store is empty.", file=sys.stderr)
            return 1
        if args.report == "latest":
            run = runs[-1]
        else:
            try:
                idx = int(args.report)
                run = next(r for r in runs if r.run_index == idx)
            except (ValueError, StopIteration):
                print(f"No run with index {args.report!r}. Run --list-runs to see valid indices.",
                      file=sys.stderr)
                return 1
        out_path = generate_report_for_run(run, output_path=args.output)
        print(f"Wrote {out_path}")
        return 0

    if args.latest:
        ids = all_trace_ids(limit=1)
        if not ids:
            print("No traces recorded yet.")
            return 1
        return 0 if render(ids[0]) else 1

    if not args.trace_id:
        parser.error("provide a trace_id, or use --latest / --list / --list-runs / --report")
    return 0 if render(args.trace_id) else 1


if __name__ == "__main__":
    sys.exit(main())
