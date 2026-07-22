"""
reset_topics.py

Ensures every topic in harness_config.DEMO_TOPICS exists on the local Kafka
broker, with partition counts read directly from contracts/topics/
kafka_topics.yaml -- never hand-invented. The registry's contract is not
modified; only ONE operational parameter is overridden for the local
single-broker dev cluster: replication_factor is forced to 1 (the
registry's replication_factor: 3 assumes a 3+ broker cluster, which
scripts/dev-env/docker-compose.yml intentionally does not run -- a
single-broker dev Kafka cannot satisfy RF=3 at all, let alone the
contract's min_insync_replicas: 2 where set). This is the same kind of
environment-specific override any team makes between local dev and
production Kafka; it changes durability, not the topic's name, schema,
partition count, or semantics.

Usage:
    python3 reset_topics.py            # create missing topics, leave existing alone
    python3 reset_topics.py --recreate # delete + recreate every demo topic (fresh state)
"""
from __future__ import annotations

import argparse
import sys

import yaml
from confluent_kafka.admin import AdminClient, NewTopic

import harness_config as cfg
from event_logger import StageEvent, log_stage


def load_registry_partition_counts() -> dict[str, int]:
    with open(cfg.KAFKA_TOPICS_YAML) as f:
        raw = yaml.safe_load(f)
    counts = {}
    for topic_name in cfg.DEMO_TOPICS:
        entry = raw.get(topic_name)
        if entry is None:
            raise KeyError(
                f"{topic_name} is in harness_config.DEMO_TOPICS but has no entry in "
                f"{cfg.KAFKA_TOPICS_YAML} -- this harness only ever uses topic names "
                f"that exist in the frozen registry."
            )
        counts[topic_name] = int(entry.get("partitions", 1))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true", help="delete and recreate every demo topic")
    args = parser.parse_args()

    admin = AdminClient({"bootstrap.servers": cfg.KAFKA_BOOTSTRAP_SERVERS})

    try:
        cluster_md = admin.list_topics(timeout=10)
    except Exception as e:  # noqa: BLE001
        log_stage(StageEvent(component="Kafka", stage="Broker Reachable", status="failed",
                              reason=f"{type(e).__name__}: {e}"))
        print(f"FAILED: cannot reach Kafka at {cfg.KAFKA_BOOTSTRAP_SERVERS}: {e}", file=sys.stderr)
        print("Start it first, e.g.: docker compose -f ../../scripts/dev-env/docker-compose.yml up -d kafka",
              file=sys.stderr)
        return 1
    log_stage(StageEvent(component="Kafka", stage="Broker Reachable", status="success"))

    partition_counts = load_registry_partition_counts()
    for t in cfg.DEMO_RETRY_TOPICS + cfg.DEMO_DLQ_TOPICS:
        partition_counts[t] = 1
    all_demo_topics = cfg.DEMO_TOPICS + cfg.DEMO_RETRY_TOPICS + cfg.DEMO_DLQ_TOPICS
    existing = set(cluster_md.topics.keys())

    if args.recreate:
        to_delete = [t for t in all_demo_topics if t in existing]
        if to_delete:
            print(f"Deleting {len(to_delete)} existing demo topic(s): {to_delete}")
            futures = admin.delete_topics(to_delete, operation_timeout=30)
            for topic, fut in futures.items():
                try:
                    fut.result()
                    log_stage(StageEvent(component="Kafka", stage="Topic Deleted", status="success", topic=topic))
                except Exception as e:  # noqa: BLE001
                    log_stage(StageEvent(component="Kafka", stage="Topic Deleted", status="failed", topic=topic,
                                          reason=str(e)))
            existing = existing - set(to_delete)

    to_create = [t for t in all_demo_topics if t not in existing]
    if not to_create:
        print("All demo topics already exist. Nothing to create.")
    else:
        new_topics = [
            NewTopic(topic, num_partitions=partition_counts[topic], replication_factor=1)
            for topic in to_create
        ]
        print(f"Creating {len(new_topics)} topic(s): {to_create}")
        futures = admin.create_topics(new_topics)
        for topic, fut in futures.items():
            try:
                fut.result()
                log_stage(StageEvent(component="Kafka", stage="Topic Created", status="success", topic=topic,
                                      extra={"partitions": partition_counts[topic], "replication_factor": 1}))
                print(f"  OK   {topic}")
            except Exception as e:  # noqa: BLE001
                log_stage(StageEvent(component="Kafka", stage="Topic Created", status="failed", topic=topic,
                                      reason=str(e)))
                print(f"  FAIL {topic}: {e}")

    print("\nFinal topic verification:")
    final_md = admin.list_topics(timeout=10)
    for topic in all_demo_topics:
        present = topic in final_md.topics
        partitions = len(final_md.topics[topic].partitions) if present else 0
        status = "EXISTS" if present else "MISSING"
        print(f"  {status:8s} {topic} (partitions={partitions})")
        log_stage(StageEvent(component="Kafka", stage="Topic Verified",
                              status="success" if present else "failed", topic=topic,
                              extra={"partitions": partitions}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
