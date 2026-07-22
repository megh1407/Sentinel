"""
Load / stress test scenarios (Phase 9, TSES §2 "Load Tests"/"Stress Tests").

Uses Locust against the agent's Kafka-facing surface via a thin harness that
publishes synthetic AgentResult events at a controlled rate and measures
sentinel.risk.score.v1 publish latency end-to-end — the same canonical
workflow TSES §9.1 exercises for correctness, driven here at volume instead
of once.

Run:
    locust -f tests/load/load_test_scenarios.py --headless \
        --users 500 --spawn-rate 50 --run-time 10m \
        --host kafka://kafka-bootstrap:9092
"""

from __future__ import annotations

import json
import random
import time
import uuid

from locust import User, between, events, task

ZONE_IDS = [f"zone-{i:03d}" for i in range(1, 201)]   # 200 zones — mid-size site
SITE_ID = "site-loadtest-01"


def _synthetic_environment_analysis(zone_id: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "environment.analysis.complete",
        "site_id": SITE_ID,
        "zone_id": zone_id,
        "correlation_id": str(uuid.uuid4()),
        "agent_id": "environmental_intelligence_agent",
        "agent_version": "2.0.3",
        "result_type": "environment_analysis",
        "confidence": round(random.uniform(0.7, 0.95), 2),
        "payload": {
            "risk_score": random.randint(20, 90),
            "confidence": round(random.uniform(0.7, 0.95), 2),
            "hazards": [{
                "hazard_type": "toxic_gas",
                "measured_value": round(random.uniform(10, 45), 1),
                "unit": "ppm",
                "threshold_ppm": 35,
                "threshold_breach": random.random() < 0.15,
                "trend": random.choice(["rising", "stable", "falling"]),
            }],
            "evidence": [f"ev-{uuid.uuid4().hex[:8]}"],
            "recommendations": [],
            "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }


class KafkaPublishClient:
    """Thin wrapper so Locust's request-event hooks can time a Kafka publish
    the same way they'd time an HTTP call — this is a load-test harness
    concern only, never a production code path."""

    def __init__(self, bootstrap_servers: str):
        from confluent_kafka import Producer  # test-only dependency
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})

    def publish(self, topic: str, payload: dict) -> None:
        start = time.perf_counter()
        try:
            self._producer.produce(topic, json.dumps(payload).encode("utf-8"))
            self._producer.flush(timeout=5)
            events.request.fire(
                request_type="KAFKA_PUBLISH",
                name=topic,
                response_time=(time.perf_counter() - start) * 1000,
                response_length=len(json.dumps(payload)),
                exception=None,
            )
        except Exception as exc:  # noqa: BLE001 — load-test harness, report and continue
            events.request.fire(
                request_type="KAFKA_PUBLISH",
                name=topic,
                response_time=(time.perf_counter() - start) * 1000,
                response_length=0,
                exception=exc,
            )


class SixDomainEventUser(User):
    """
    Simulates the six upstream Intelligence Agents publishing analysis
    events at their registry-documented cadences (Phase 1 §4.7) — this is
    the "normal operation" and "sustained high load" scenario depending on
    wait_time tuning; see NORMAL / PEAK / BURST profiles below.
    """

    wait_time = between(0.3, 2.0)  # normal-operation profile; override per scenario

    def on_start(self) -> None:
        self.client_ = KafkaPublishClient(self.host.replace("kafka://", ""))

    @task(6)
    def publish_environment_analysis(self) -> None:
        zone_id = random.choice(ZONE_IDS)
        self.client_.publish(
            "sentinel.environment.analysis.v1", _synthetic_environment_analysis(zone_id)
        )

    @task(3)
    def publish_permit_analysis(self) -> None:
        zone_id = random.choice(ZONE_IDS)
        self.client_.publish("sentinel.permit.analysis.v1", {
            "event_id": str(uuid.uuid4()), "zone_id": zone_id, "site_id": SITE_ID,
            "payload": {"permit_id": str(uuid.uuid4()), "risk_score": random.randint(10, 80),
                        "confidence": 0.8, "conflicts": [], "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
        })

    @task(4)
    def publish_worker_analysis(self) -> None:
        zone_id = random.choice(ZONE_IDS)
        self.client_.publish("sentinel.worker.analysis.v1", {
            "event_id": str(uuid.uuid4()), "zone_id": zone_id, "site_id": SITE_ID,
            "payload": {"worker_id": f"W-{random.randint(10000,99999)}",
                        "risk_score": random.randint(10, 80), "confidence": 0.85,
                        "safety_status": random.choice(["safe", "at_risk"]),
                        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
        })


class BurstTrafficUser(SixDomainEventUser):
    """Burst-traffic scenario: short, sharp spikes (Phase 9 'Burst traffic')."""
    wait_time = between(0.01, 0.1)


class SustainedHighLoadUser(SixDomainEventUser):
    """Sustained high load — steady elevated rate for the full run duration."""
    wait_time = between(0.05, 0.3)
