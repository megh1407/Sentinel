"""
ppe_vision_adapter.py

DEMO / VISION LAYER -- NOT PART OF worker_safety_agent, NOT A REGISTERED
AGENT, NOT WIRED TO KAFKA IN PRODUCTION.

Per the master prompt's section 4 ("Separate Vision Inference from Worker
Safety Reasoning"), this module plays the role of the producer named
`ppe-vision-service` in contracts/topics/kafka_topics.yaml (one of two
declared producers of sentinel.worker.events.v1, alongside rtls-gateway --
see that file). That producer role is named in the frozen registry but has
no implementation anywhere in this repo. This module fills in that
already-named gap; it does NOT invent a new agent, topic, or contract.

It deliberately does NOT live under agents/ppe-detection-agent/ --
that folder's own OWNERSHIP.md explicitly concludes PPE reasoning belongs
in worker_safety_agent and that the folder "should not be assigned to an
engineer as standalone work." This module respects that conclusion: it
contains no worker-safety reasoning, no compliance logic, no risk scoring,
and is not registered as an agent anywhere. It only does the one thing
named as `ppe-vision-service`'s job: turn frames into WorkerEvent.

Responsibility boundary (enforced, not just stated):
    YOLO inference -> detections -> WorkerEventV1.payload.ppe_status
This module MUST NOT and does NOT:
    - decide compliance (that's ppe_compliance_service.py, inside
      worker_safety_agent, consuming the WorkerEvent this module produces)
    - decide risk_score, permit approval, or zone clearance
    - publish to any topic other than sentinel.worker.events.v1
    - construct anything other than WorkerEventV1

YOLO CLASS -> ppe_status KEY MAPPING.

Actual trained classes (corrected -- supersedes an earlier draft of this
file that assumed boots/gloves/goggles/helmet/person/vest; the real model
has a DIFFERENT and smaller class list, with explicit negative classes for
two of the three items):

    person      -- NOT written to ppe_status; used only for the
                    worker-association gap below.
    helmet      -- positive evidence ppe_status["helmet"] = True
    no-helmet   -- positive evidence ppe_status["helmet"] = False
    vest        -- positive evidence ppe_status["vest"]   = True
    no-vest     -- positive evidence ppe_status["vest"]   = False
    gloves      -- positive evidence ppe_status["gloves"] = True
                    (no "no-gloves" class is trained -- see below)

This is a materially different mapping problem than a same-named
detected/absent pair, and worth spelling out precisely rather than
assuming a pattern from the first three items also applies to the
fourth:

  - For "helmet" and "vest", the model gives an EXPLICIT negative signal
    (a "no-helmet"/"no-vest" box IS a detection, not an absence of one).
    A frame can therefore produce three distinct evidentiary states per
    item, not two: positive-only, negative-only, or BOTH (a genuine model
    disagreement within one frame -- e.g. two overlapping/ambiguous boxes).
    See _resolve_pair() below for how the "both" case is handled -- this
    is a demo-layer policy decision (not a contract question), and it is
    documented, not silently defaulted.

  - For "gloves", there is no negative class at all. The only signal
    available is "detected" or "not detected in this frame" -- so, exactly
    as in the original single-class-per-item design, absence of a
    detection is treated as False (matching ppe_compliance_service.py's
    own stated philosophy: "absence of evidence for a required safety item
    is not evidence of its presence").

  - For "helmet"/"vest" specifically, if NEITHER the positive nor the
    negative class fires (person occluded, box missed, whatever), this
    adapter also reports False, for the same fail-safe reason -- an
    unconfirmed item is not a confirmed item.

This mapping again requires no contract change: WorkerEventPayload.ppe_status
is a generic Avro `map<string, boolean>` / Pydantic `dict[str, bool]` (the
REAL generated model -- see worker_event_v1.py), not a fixed field set, so
adding/removing tracked item names is a change to this adapter only.

[PLATFORM GAP -- WORKER/PPE ASSOCIATION]
The model detects `person` and PPE-item boxes independently; nothing in
the frozen contracts (WorkerEvent, WorkerEventPayload, or any topic)
provides a mechanism to associate a given PPE-item detection with a
specific `person` detection when a frame contains more than one worker
(no tracking_id, no per-worker bounding-box correlation, no re-ID feature
anywhere in this repo's contracts). Evidence: WorkerEventPayload has a
single flat `worker_id: str` and a single flat `ppe_status: dict[str, bool]`
-- there is no per-detection worker_id anywhere in the contract to assign
PPE items to different people in the same event.
Possible architectural decisions (not decided here, not invented as a
silent default): (a) one WorkerEvent per tracked person, requiring a
tracking_id contract addition; (b) a bounding-box-overlap heuristic
computed entirely inside this vision layer, with its own confidence field
added to the contract; (c) restrict this contract's use to single-worker
zones only, documented as a deployment constraint rather than a technical
one.
Per the master prompt's explicit allowance ("For a demo-only single-worker
frame, a temporary deterministic association may be allowed only if
explicitly isolated inside a demo adapter and clearly marked as
non-production"): this module implements exactly that, and no more. It
raises rather than guesses when a frame contains more than one `person`
detection, instead of silently picking one.
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Protocol

# NOTE: sentinel_contracts is imported lazily, inside build_worker_event()
# below, not here at module level. That package lives elsewhere in the
# sentinel monorepo and isn't needed for detection/inference -- only for
# constructing a real WorkerEventV1 to publish to Kafka. Importing it here
# would make this whole module (including UltralyticsYOLODetector) fail to
# load in any environment that doesn't have sentinel_contracts installed,
# e.g. a standalone test/video-check environment like demo/run_video_test.py.

# Items this adapter tracks in ppe_status, and which model classes count as
# positive/negative evidence for each. Only "helmet" and "vest" have a
# trained negative class today; "gloves" does not (see module docstring).
PPE_ITEM_POSITIVE_CLASS: dict[str, str] = {"helmet": "helmet", "vest": "vest", "gloves": "gloves"}
PPE_ITEM_NEGATIVE_CLASS: dict[str, str] = {"helmet": "no-helmet", "vest": "no-vest"}  # gloves: none trained

PPE_ITEMS = tuple(PPE_ITEM_POSITIVE_CLASS.keys())
ALL_MODEL_CLASSES = ("person",) + tuple(PPE_ITEM_POSITIVE_CLASS.values()) + tuple(PPE_ITEM_NEGATIVE_CLASS.values())


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


class Detector(Protocol):
    """Anything that turns an image into a list of Detection is a valid
    backend -- real Ultralytics YOLO, a different framework, or (for this
    demo, since the real model is still training per the task brief) a
    synthetic/fixture backend. worker_safety_agent never imports this
    Protocol or any implementation of it; only this module does."""

    def predict(self, image_path: str) -> list[Detection]: ...


class UltralyticsYOLODetector:
    """Real backend, for when a trained weights file exists. Ultralytics is
    imported lazily (inside __init__, not at module import time) so this
    module stays importable -- and unit-testable -- in environments (like
    this one, since the model is still training) that don't have a weights
    file or don't want the torch/ultralytics dependency installed."""

    def __init__(self, weights_path: str, confidence_threshold: float = 0.5, imgsz: int = 640):
        from ultralytics import YOLO  # deferred import, see docstring

        self._model = YOLO(weights_path)
        self._confidence_threshold = confidence_threshold
        self._imgsz = imgsz  # inference resolution; larger helps small objects
        # (e.g. helmets in a wide/crowd shot) at the cost of slower inference.

    def predict(self, image_path: str) -> list[Detection]:
        return self._run(image_path)

    def predict_frame(self, frame) -> list[Detection]:
        """Same as predict(), but takes an in-memory BGR numpy frame (e.g.
        from cv2.VideoCapture.read()) instead of a file path. Added for
        continuous video/live-camera use -- image_path-only inference would
        require writing every frame to disk first, which is wasteful and
        slow for a per-frame loop."""
        return self._run(frame)

    def _run(self, source) -> list[Detection]:
        results = self._model.predict(source, conf=self._confidence_threshold, imgsz=self._imgsz, verbose=False)
        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                class_name = result.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                detections.append(Detection(class_name, confidence, (x1, y1, x2, y2)))
        return detections


class SyntheticDetector:
    """DEMO-ONLY backend. The real model (per the task brief) is still
    being trained, so there is no weights file to load. This backend
    returns a fixed, caller-supplied detection list instead of running
    inference -- it exists so the rest of this pipeline (mapping,
    association, WorkerEvent construction, Kafka publish) can be proven for
    real today, without pretending inference happened. Never used unless
    explicitly constructed by a caller in demo/ or tests/."""

    def __init__(self, fixed_detections: list[Detection]):
        self._fixed_detections = fixed_detections

    def predict(self, image_path: str) -> list[Detection]:
        return list(self._fixed_detections)


def _resolve_item(item: str, detections: list[Detection]) -> tuple[bool, bool]:
    """Returns (value, was_conflict) for one tracked PPE item.

    Conflict policy (a demo-layer judgment call, not a contract question,
    and documented rather than silently applied): if BOTH the positive and
    negative class fire in the same frame for an item that has a trained
    negative class, this is a genuine model disagreement. Resolved
    fail-safe: compliant (True) only if the positive detection's
    confidence is STRICTLY greater than the negative's; a tie or a lower
    positive confidence resolves to non-compliant. Getting this wrong in
    the "looks compliant" direction is the worse failure mode for a safety
    system, so ties are broken toward the violation, not away from it.
    """
    positive_class = PPE_ITEM_POSITIVE_CLASS[item]
    negative_class = PPE_ITEM_NEGATIVE_CLASS.get(item)

    positive_confidences = [d.confidence for d in detections if d.class_name == positive_class]
    negative_confidences = (
        [d.confidence for d in detections if negative_class and d.class_name == negative_class]
        if negative_class else []
    )

    has_positive = bool(positive_confidences)
    has_negative = bool(negative_confidences)

    if has_positive and has_negative:
        return (max(positive_confidences) > max(negative_confidences)), True
    if has_positive:
        return True, False
    if has_negative:
        return False, False
    return False, False  # neither fired -> unconfirmed -> treated as non-compliant, fail-safe


def detections_to_ppe_status(detections: list[Detection]) -> dict[str, bool]:
    """Every tracked item (PPE_ITEMS) is always present as a key -- an item
    with no positive evidence is explicitly False, never omitted, matching
    ppe_compliance_service.py's requirement that ppe_status not blur
    "confirmed absent" with "not checked" (see that module's docstring)."""
    return {item: _resolve_item(item, detections)[0] for item in PPE_ITEMS}


def detect_ppe_status_conflicts(detections: list[Detection]) -> list[str]:
    """Items where BOTH the positive and negative class fired in the same
    frame -- worth surfacing to observability/logging even though
    detections_to_ppe_status() already resolved a value for them (see
    _resolve_item()'s docstring for the resolution policy)."""
    return [item for item in PPE_ITEMS if _resolve_item(item, detections)[1]]


def count_person_detections(detections: list[Detection]) -> int:
    return sum(1 for d in detections if d.class_name == "person")


class MultiWorkerFrameNotSupported(Exception):
    """Raised instead of silently assigning PPE detections to an arbitrary
    worker when a frame contains more than one `person` detection. See this
    module's docstring, "PLATFORM GAP -- WORKER/PPE ASSOCIATION"."""


def build_worker_event(
    *,
    detections: list[Detection],
    worker_id: str,
    site_id: str,
    zone_id: str,
    demo_single_worker_override: bool = False,
):
    """Constructs a real WorkerEventV1 from a detection list.

    `worker_id` must be supplied by the caller (e.g. from an RTLS badge
    read, a separate identity system, or -- for this demo only -- a fixed
    test value) -- this function does not invent one, since no contract
    field or mechanism exists to derive it from pixels alone.

    Raises MultiWorkerFrameNotSupported if more than one `person` is
    detected, unless `demo_single_worker_override=True` is passed
    explicitly (mirrors the master prompt's demo-only allowance; the
    caller opting in is the "explicitly isolated" part -- see
    demo/run_pipeline_demo.py for the only place this repo sets it True).
    """
    from sentinel_contracts.common.metadata import Environment, Metadata
    from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1

    person_count = count_person_detections(detections)
    if person_count > 1 and not demo_single_worker_override:
        raise MultiWorkerFrameNotSupported(
            f"{person_count} person detections in one frame, but the frozen WorkerEvent "
            "contract has no per-detection worker association mechanism (single flat "
            "worker_id/ppe_status per event). See this module's docstring for the "
            "platform-gap options. Pass demo_single_worker_override=True only in a "
            "clearly-marked demo/test path, per the master prompt's explicit allowance."
        )

    ppe_status = detections_to_ppe_status(detections)

    return WorkerEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(),
        producer_service="ppe-vision-service",
        producer_version="0.1.0-demo",
        site_id=site_id,
        zone_id=zone_id,
        partition_key=zone_id,
        metadata=Metadata(schema_id=200, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=WorkerEventKind.PPE_STATUS, ppe_status=ppe_status),
    )