"""
run_pipeline_demo.py

DEMO ONLY -- not deployed, not registered, not reachable from main.py.

Proves the real platform path end to end using a SyntheticDetector (the
real YOLO model is still training, per the task brief -- see
ppe_vision_adapter.py's SyntheticDetector docstring), and reports which
pipeline stage it reached, per the master prompt's numbered-stage
diagnostic format (section 14).

Run: python run_pipeline_demo.py   (from this directory, with the repo's
venv active; needs no Kafka broker, no Redis, no Postgres -- InMemoryTransport
and a no-backend StateContainer stand in, same as the test suite).
"""
from __future__ import annotations

import sys
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "worker_safety_agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

STAGES = [
    "MODEL_LOAD", "FRAME_INFERENCE", "PPE_RESULT_MAPPING", "WORKER_EVENT_CONSTRUCTION",
    "KAFKA_INPUT_PUBLISH", "WORKER_AGENT_CONSUME", "PPE_COMPLIANCE_EVALUATION",
]


def main() -> int:
    trace_id = str(uuid.uuid4())
    stage = None
    try:
        stage = "MODEL_LOAD"
        from ppe_vision_adapter import Detection, SyntheticDetector, build_worker_event

        # No weights file exists (model still training) -- SyntheticDetector
        # stands in, explicitly, rather than silently faking a real model load.
        # Real trained classes: person, helmet, no-helmet, vest, no-vest, gloves.
        detector = SyntheticDetector(fixed_detections=[
            Detection("person", 0.97, (10, 10, 200, 400)),
            Detection("helmet", 0.95, (40, 10, 120, 60)),
            Detection("no-vest", 0.88, (30, 100, 170, 260)),
            # gloves NOT detected in this synthetic frame, and the model
            # explicitly saw "no-vest" (not merely an absence of "vest") --
            # both surface as real violations through the pipeline below.
        ])
        print(f"[{stage}] OK -- SyntheticDetector (demo stand-in; no real weights file)")

        stage = "FRAME_INFERENCE"
        detections = detector.predict("demo/fixtures/synthetic_frame.jpg")
        print(f"[{stage}] OK -- {len(detections)} detections")

        stage = "PPE_RESULT_MAPPING"
        from ppe_vision_adapter import detections_to_ppe_status
        ppe_status = detections_to_ppe_status(detections)
        print(f"[{stage}] OK -- {ppe_status}")

        stage = "WORKER_EVENT_CONSTRUCTION"
        event = build_worker_event(detections=detections, worker_id="W-DEMO-1", site_id="SITE-01", zone_id="Z-104")
        print(f"[{stage}] OK -- event_id={event.event_id}")

        stage = "KAFKA_INPUT_PUBLISH"
        from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
        from sentinel_contracts.events.worker_event_v1 import WorkerEventV1

        schema_provider = LocalSchemaProvider()
        producer_transport = InMemoryTransport(client_id="demo-producer")
        consumer_transport = InMemoryTransport(client_id="demo-consumer")
        producer = EventProducer(producer_transport, schema_provider)
        producer.publish("sentinel.worker.events.v1", event)
        print(f"[{stage}] OK -- published to sentinel.worker.events.v1")

        stage = "WORKER_AGENT_CONSUME"
        from sentinel_agent_sdk import AgentRunner
        from sentinel_state import StateContainer
        from worker_safety_agent import WorkerSafetyAgent
        from zone_ppe_requirements import ZonePPERequirements

        consumer = EventConsumer(consumer_transport, schema_provider, {"WorkerEvent": WorkerEventV1}, group_id="demo-worker-safety")
        agent = WorkerSafetyAgent(zone_ppe_requirements=ZonePPERequirements(per_zone={"Z-104": ["helmet", "vest", "gloves"]}))
        runner = AgentRunner(
            agent, consumer=consumer, producer=producer, state_container=StateContainer(),
            input_topics=["sentinel.worker.events.v1"], output_topic="sentinel.worker.analysis.v1",
        )
        runner.run(max_iterations=1, max_empty_polls=5)
        print(f"[{stage}] OK -- consumed and processed")

        stage = "PPE_COMPLIANCE_EVALUATION"
        result = agent.last_results.get("W-DEMO-1")
        if result is None:
            raise RuntimeError("agent did not record a result for W-DEMO-1")
        print(f"[{stage}] OK -- compliant={result.is_fully_compliant} violations={result.ppe_violations}")

        print()
        print("Pipeline reached the end of what's currently supported.")
        print("WORKER_ANALYSIS_CONSTRUCTION / KAFKA_OUTPUT_PUBLISH NOT ATTEMPTED:")
        print("  blocked by the documented, experimentally-proven gap in")
        print("  worker_safety_agent.py / main.py (see also")
        print("  tests/integration/test_worker_analysis_publish_gap.py).")
        return 0

    except Exception as exc:
        print()
        print("FAILED STAGE:", stage)
        print("TRACE ID:", trace_id)
        print("EXCEPTION:", repr(exc))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
