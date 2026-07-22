"""
consumer_monitor.py

Answers the brief's "Agent Verification" checklist per agent -- Running,
Events Received, Events Processed, Events Failed, Average Processing Time,
Output Events Produced -- by reading event_logger's store (which every
worker/simulator already writes to as it runs). This is the agent-level
view; kafka_topic_monitor.py is the broker-level view.

Usage:
    python3 consumer_monitor.py            # one-shot report
    python3 consumer_monitor.py --watch 5
"""
from __future__ import annotations

import argparse
import sys
import time

from event_history import latency_stats, stage_counts

AGENTS = {
    "Environmental Agent": {
        "received_stage": "SensorSnapshotAggregator Ingest",
        "processing_stage": "SensorSnapshotAggregator Ingest",
        "produced_stage": None,  # never produces today -- see environmental_agent_worker.py
    },
    "Zone Agent": {
        "received_stage": "ZoneState Computed",
        "processing_stage": "ZoneState Computed",
        "produced_stage": "Kafka Publish",
    },
}


def report() -> None:
    print(f"\n{'=' * 70}\nAgent Consumer Monitor -- {time.strftime('%H:%M:%S')}\n{'=' * 70}")
    counts = stage_counts()
    by_component_stage_status: dict[tuple[str, str, str], int] = {
        (c, s, st): n for c, s, st, n in counts
    }

    for agent_name, cfg_ in AGENTS.items():
        received = sum(n for (c, s, st), n in by_component_stage_status.items()
                        if c == agent_name and s == cfg_["received_stage"])
        processed = sum(n for (c, s, st), n in by_component_stage_status.items()
                         if c == agent_name and s == cfg_["processing_stage"] and st == "success")
        failed = sum(n for (c, s, st), n in by_component_stage_status.items()
                     if c == agent_name and st == "failed")
        produced = 0
        if cfg_["produced_stage"]:
            produced = sum(n for (c, s, st), n in by_component_stage_status.items()
                            if c == agent_name and s == cfg_["produced_stage"] and st == "success")

        lat = latency_stats(agent_name, cfg_["processing_stage"])

        print(f"\n{agent_name}")
        print(f"  Events received (seen):   {received}")
        print(f"  Events processed (ok):    {processed}")
        print(f"  Events failed:            {failed}")
        print(f"  Output events produced:   {produced}")
        print(f"  Avg processing time:      {lat['avg_ms']} ms" if lat["avg_ms"] is not None
              else "  Avg processing time:      no samples yet")
        print(f"  p95 processing time:      {lat['p95_ms']} ms" if lat["p95_ms"] is not None else "")

    # Anything logged but not attributed to a known agent stage above --
    # surfaced explicitly rather than silently dropped from the report.
    other = {(c, s, st): n for (c, s, st), n in by_component_stage_status.items()
             if c not in AGENTS}
    if other:
        print(f"\nOther components observed: {sorted({c for c, _, _ in other})}")
    print()


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
