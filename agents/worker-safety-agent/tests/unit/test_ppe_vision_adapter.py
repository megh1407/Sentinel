import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "demo"))

import pytest

from ppe_vision_adapter import (
    Detection,
    MultiWorkerFrameNotSupported,
    SyntheticDetector,
    build_worker_event,
    count_person_detections,
    detect_ppe_status_conflicts,
    detections_to_ppe_status,
)


def _det(name: str, confidence: float = 0.9) -> Detection:
    return Detection(class_name=name, confidence=confidence, bbox_xyxy=(0.0, 0.0, 10.0, 10.0))


def test_all_positive_classes_present_is_fully_compliant_mapping():
    detections = [_det("person"), _det("helmet"), _det("vest"), _det("gloves")]
    status = detections_to_ppe_status(detections)
    assert status == {"helmet": True, "vest": True, "gloves": True}


def test_explicit_negative_class_maps_to_false():
    """no-helmet / no-vest are themselves detections, not an absence --
    this is the behavior that differs from a simple presence/absence
    model and is worth testing directly."""
    detections = [_det("person"), _det("no-helmet"), _det("no-vest")]
    status = detections_to_ppe_status(detections)
    assert status == {"helmet": False, "vest": False, "gloves": False}


def test_gloves_has_no_negative_class_absence_means_false():
    detections = [_det("person"), _det("helmet"), _det("vest")]  # no gloves, no "no-gloves" class exists
    status = detections_to_ppe_status(detections)
    assert status["gloves"] is False


def test_neither_positive_nor_negative_detected_defaults_false_failsafe():
    detections = [_det("person")]  # nothing said about helmet/vest/gloves at all
    status = detections_to_ppe_status(detections)
    assert status == {"helmet": False, "vest": False, "gloves": False}


def test_conflicting_helmet_detections_resolve_by_higher_confidence():
    detections = [_det("person"), _det("helmet", confidence=0.9), _det("no-helmet", confidence=0.4)]
    status = detections_to_ppe_status(detections)
    assert status["helmet"] is True  # positive confidence strictly greater
    assert detect_ppe_status_conflicts(detections) == ["helmet"]


def test_conflicting_helmet_detections_tie_resolves_failsafe_to_false():
    detections = [_det("person"), _det("helmet", confidence=0.7), _det("no-helmet", confidence=0.7)]
    status = detections_to_ppe_status(detections)
    assert status["helmet"] is False  # tie -> fail-safe non-compliant
    assert detect_ppe_status_conflicts(detections) == ["helmet"]


def test_no_conflict_when_only_one_side_fires():
    detections = [_det("person"), _det("vest", confidence=0.8)]
    assert detect_ppe_status_conflicts(detections) == []


def test_person_and_negative_classes_never_leak_into_ppe_status_keys():
    detections = [_det("person"), _det("no-helmet"), _det("gloves")]
    status = detections_to_ppe_status(detections)
    assert set(status.keys()) == {"helmet", "vest", "gloves"}
    assert "person" not in status
    assert "no-helmet" not in status


def test_count_person_detections():
    assert count_person_detections([_det("person"), _det("helmet"), _det("person")]) == 2
    assert count_person_detections([_det("helmet")]) == 0


def test_single_worker_frame_builds_real_worker_event():
    detections = [_det("person"), _det("helmet"), _det("vest")]
    event = build_worker_event(detections=detections, worker_id="W-1", site_id="SITE-01", zone_id="Z-104")
    assert event.payload.worker_id == "W-1"
    assert event.payload.ppe_status["helmet"] is True
    assert event.payload.ppe_status["gloves"] is False


def test_multi_worker_frame_raises_by_default():
    detections = [_det("person"), _det("person"), _det("helmet")]
    with pytest.raises(MultiWorkerFrameNotSupported):
        build_worker_event(detections=detections, worker_id="W-1", site_id="SITE-01", zone_id="Z-104")


def test_multi_worker_frame_allowed_only_with_explicit_demo_override():
    detections = [_det("person"), _det("person"), _det("helmet")]
    event = build_worker_event(
        detections=detections, worker_id="W-1", site_id="SITE-01", zone_id="Z-104",
        demo_single_worker_override=True,
    )
    assert event.payload.worker_id == "W-1"  # still deterministic, still a single id -- demo-only, documented


def test_synthetic_detector_returns_fixed_list_without_running_inference():
    fixed = [_det("helmet")]
    detector = SyntheticDetector(fixed_detections=fixed)
    assert detector.predict("irrelevant/path.jpg") == fixed
