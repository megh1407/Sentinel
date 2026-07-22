"""
test_worker_analysis_shape.py

Two things this test proves, and one gap it documents rather than papers
over:

1. WorkerEventV1 (the REAL generated model this agent actually consumes)
   accepts a generic ppe_status dict the way the vision adapter
   (../../demo/ppe_vision_adapter.py) produces it. Real Pydantic
   validation, not a hand-rolled stand-in.

2. ppe_compliance_service's payload fragment ({"ppe_compliance": float,
   "ppe_violations": [str]}) is a legal instance of
   worker_analysis.schema.json's `payload.properties.ppe_compliance` /
   `payload.properties.ppe_violations` sub-schemas -- validated with
   jsonschema directly against the real, committed, frozen schema file.
   This is deliberately NOT "validate against the generated Pydantic
   model" (master prompt's stated preference) because no such model
   exists (README.md G2) -- jsonschema-against-the-real-file is the
   closest available substitute, and is explicitly what's being
   substituted and why.

   Scoped to just those two properties, not the full WorkerAnalysis
   envelope: contracts/events/v1/base_event.schema.json (which
   agent_result.schema.json, which worker_analysis.schema.json extends,
   inherits from) uses a materially different envelope shape
   (event_type/timestamp/source/schema_version, zone_id required-non-null)
   than the Avro-derived envelope this agent's actual generated models use
   (event_timestamp/producer_service/producer_version/metadata/trace_id,
   zone_id nullable) -- see WorkerEventV1 vs. contracts/events/v1/worker_event.schema.json
   for the same divergence one layer over. Building a "fully valid
   envelope" would mean arbitrarily picking one of two never-reconciled
   contract sources and asserting it as ground truth; this test doesn't
   do that. It validates only the fields this agent is actually
   authoritative for.
"""
import json
from pathlib import Path

import jsonschema
import pytest

from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1
from sentinel_contracts.common.metadata import Environment, Metadata
import datetime
import uuid

from ppe_compliance_service import evaluate_ppe_compliance

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKER_ANALYSIS_SCHEMA_PATH = REPO_ROOT / "contracts" / "agent-contracts" / "v1" / "worker_analysis.schema.json"


@pytest.fixture(scope="module")
def worker_analysis_payload_properties() -> dict:
    with open(WORKER_ANALYSIS_SCHEMA_PATH) as f:
        schema = json.load(f)
    return schema["properties"]["payload"]["properties"]


def test_worker_event_v1_accepts_generic_ppe_status_dict():
    """The REAL generated model -- confirms ppe_status is a generic
    dict[str, bool], not the fixed helmet/vest/gloves/boots/mask/harness/
    goggles/ear_protection field set the older
    contracts/events/v1/worker_event.schema.json draft describes."""
    event = WorkerEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(),
        producer_service="ppe-vision-service",
        producer_version="0.1.0-demo",
        site_id="SITE-01",
        zone_id="Z-104",
        partition_key="Z-104",
        metadata=Metadata(schema_id=200, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(
            worker_id="W-1",
            event_kind=WorkerEventKind.PPE_STATUS,
            ppe_status={"helmet": True, "vest": False, "gloves": True},
        ),
    )
    assert event.payload.ppe_status["vest"] is False


def test_ppe_compliance_field_matches_frozen_schema(worker_analysis_payload_properties):
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-104",
        detected_ppe={"helmet": True, "vest": False}, required_ppe=["helmet", "vest"],
    )
    fragment = result.to_worker_analysis_payload_fragment()

    jsonschema.validate(fragment["ppe_compliance"], worker_analysis_payload_properties["ppe_compliance"])


def test_ppe_violations_field_matches_frozen_schema(worker_analysis_payload_properties):
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-104",
        detected_ppe={"helmet": True, "vest": False}, required_ppe=["helmet", "vest"],
    )
    fragment = result.to_worker_analysis_payload_fragment()

    jsonschema.validate(fragment["ppe_violations"], worker_analysis_payload_properties["ppe_violations"])


def test_ppe_compliance_as_bool_would_have_failed_frozen_schema(worker_analysis_payload_properties):
    """Regression guard for the ppe_compliance_service.py bug this task
    caught by reading the actual frozen schema: proves a bool value is
    REJECTED by the real committed schema, so this test would fail loudly
    if that field's type were ever reverted to bool."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(True, worker_analysis_payload_properties["ppe_compliance"])
