"""
kafka_topic_monitor.py

Everything the brief's "Kafka Verification" checklist asks for that's
observable from the broker's own metadata/consumer-group APIs, via
confluent_kafka's AdminClient -- not from event_logger. This is the layer
that answers "is Kafka itself healthy", independent of whether any agent
is running correctly.

Usage:
    python3 kafka_topic_monitor.py            # one-shot report
    python3 kafka_topic_monitor.py --watch 5   # refresh every 5s
"""
from __future__ import annotations

import argparse
import sys
import time

from confluent_kafka import Consumer, TopicPartition
from confluent_kafka.admin import AdminClient

import harness_config as cfg

ALL_MONITORED_TOPICS = cfg.DEMO_TOPICS + cfg.DEMO_RETRY_TOPICS + cfg.DEMO_DLQ_TOPICS
GROUP_INPUT_TOPICS = {
    cfg.CONSUMER_GROUP_ENV_AGENT: [cfg.TOPIC_SENSOR_EVENTS],
    cfg.CONSUMER_GROUP_ZONE_AGENT: [cfg.TOPIC_SENSOR_EVENTS, cfg.TOPIC_WORKER_EVENTS, cfg.TOPIC_PERMIT_EVENTS],
}


def compute_lag(admin: AdminClient, group_id: str, topics: list[str]) -> dict[str, int] | None:
    """Real lag: high watermark (via a throwaway Consumer, since AdminClient
    itself has no watermark API) minus this group's last committed offset,
    per partition, summed per topic. Returns None if the group has no
    committed offsets yet (hasn't consumed anything)."""
    probe = Consumer({"bootstrap.servers": cfg.KAFKA_BOOTSTRAP_SERVERS, "group.id": group_id,
                       "enable.auto.commit": False})
    try:
        cluster_md = admin.list_topics(timeout=10)
        partitions = []
        for topic in topics:
            if topic not in cluster_md.topics:
                continue
            for p in cluster_md.topics[topic].partitions:
                partitions.append(TopicPartition(topic, p))

        committed = probe.committed(partitions, timeout=10)
        lag_by_topic: dict[str, int] = {t: 0 for t in topics}
        any_committed = False
        for tp in committed:
            if tp.offset is None or tp.offset < 0:
                continue  # no committed offset for this partition yet
            any_committed = True
            low, high = probe.get_watermark_offsets(tp, timeout=10, cached=False)
            lag_by_topic[tp.topic] = lag_by_topic.get(tp.topic, 0) + max(0, high - tp.offset)
        return lag_by_topic if any_committed else None
    finally:
        probe.close()


def report(admin: AdminClient) -> bool:
    healthy = True
    print(f"\n{'=' * 70}\nKafka Topic Monitor -- {time.strftime('%H:%M:%S')}\n{'=' * 70}")

    try:
        cluster_md = admin.list_topics(timeout=10)
    except Exception as e:  # noqa: BLE001
        print(f"BROKER UNREACHABLE at {cfg.KAFKA_BOOTSTRAP_SERVERS}: {e}")
        return False
    print(f"Broker reachable: {cfg.KAFKA_BOOTSTRAP_SERVERS}  ({len(cluster_md.brokers)} broker(s))")

    print(f"\n{'Topic':<40s} {'Exists':<8s} {'Partitions':<11s}")
    for topic in ALL_MONITORED_TOPICS:
        exists = topic in cluster_md.topics
        n_partitions = len(cluster_md.topics[topic].partitions) if exists else 0
        if not exists:
            healthy = False
        print(f"{topic:<40s} {'yes' if exists else 'NO':<8s} {n_partitions:<11d}")

    print(f"\n{'Consumer Group':<35s} {'State':<12s} {'Members':<9s} {'Lag (sum)':<10s}")
    try:
        group_futures = admin.list_consumer_groups()
        group_result = group_futures.result()
        known_groups = {g.group_id for g in group_result.valid}
    except Exception as e:  # noqa: BLE001
        print(f"  could not list consumer groups: {e}")
        known_groups = set()

    for group_id, topics in GROUP_INPUT_TOPICS.items():
        if group_id not in known_groups:
            print(f"{group_id:<35s} {'NOT SEEN YET':<12s} {'-':<9s} {'-':<10s}")
            continue
        try:
            desc_futures = admin.describe_consumer_groups([group_id])
            desc = desc_futures[group_id].result()
            state = desc.state.name if hasattr(desc.state, "name") else str(desc.state)
            n_members = len(desc.members)

            lag_by_topic = compute_lag(admin, group_id, topics)
            lag_str = str(sum(lag_by_topic.values())) if lag_by_topic is not None else "no commits yet"

            print(f"{group_id:<35s} {state:<12s} {n_members:<9d} {lag_str:<10s}")
            if lag_by_topic:
                for t, lag in lag_by_topic.items():
                    print(f"    {t:<45s} lag={lag}")
        except Exception as e:  # noqa: BLE001
            print(f"{group_id:<35s} ERROR describing group: {e}")
            healthy = False

    print(f"\n{'DLQ / Retry topic':<40s} {'Note'}")
    for topic in cfg.DEMO_DLQ_TOPICS:
        print(f"{topic:<40s} present in cluster -- check message count via `kafka-run-class "
              f"kafka.tools.GetOffsetShell --topic {topic}` for a definitive count")

    print()
    return healthy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", type=float, default=None, help="refresh interval in seconds (default: run once)")
    args = parser.parse_args()

    admin = AdminClient({"bootstrap.servers": cfg.KAFKA_BOOTSTRAP_SERVERS})

    if args.watch is None:
        return 0 if report(admin) else 1

    try:
        while True:
            report(admin)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
