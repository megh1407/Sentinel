"""
test_ppe_compliance_service.py

ppe_compliance_service is class-agnostic (it operates on whatever string
keys required_ppe/detected_ppe use -- see its own docstring), so these
tests exercise it with the actual trained PPE items (helmet, vest, gloves
-- see demo/ppe_vision_adapter.py for the real YOLO class list and why
there are only three tracked items, not five) rather than an assumed set.

Master prompt section 12's required unit-test matrix: missing each
required item individually; all PPE present; malformed input (None
ppe_status); unknown PPE key; empty required_ppe.
"""
from ppe_compliance_service import evaluate_ppe_compliance


REAL_ITEMS = ["helmet", "vest", "gloves"]


def _full_detection(missing: str | None = None) -> dict[str, bool]:
    return {item: (item != missing) for item in REAL_ITEMS}


def test_all_ppe_present_is_fully_compliant():
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-1", detected_ppe=_full_detection(), required_ppe=REAL_ITEMS
    )
    assert result.is_fully_compliant
    assert result.ppe_violations == []
    assert result.ppe_compliance_score == 1.0


def test_missing_helmet_is_a_violation():
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-1", detected_ppe=_full_detection(missing="helmet"), required_ppe=REAL_ITEMS
    )
    assert not result.is_fully_compliant
    assert result.ppe_violations == ["helmet"]
    assert result.ppe_compliance_score == 2 / 3


def test_missing_vest_is_a_violation():
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-1", detected_ppe=_full_detection(missing="vest"), required_ppe=REAL_ITEMS
    )
    assert result.ppe_violations == ["vest"]


def test_missing_gloves_is_a_violation():
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-1", detected_ppe=_full_detection(missing="gloves"), required_ppe=REAL_ITEMS
    )
    assert result.ppe_violations == ["gloves"]


def test_none_ppe_status_with_required_items_is_full_non_compliance():
    """Malformed/absent WorkerEvent.payload.ppe_status (the field is
    nullable -- see worker_event_v1.py). Absence of evidence for a required
    item must not be treated as evidence of presence."""
    result = evaluate_ppe_compliance(worker_id="W-1", zone_id="Z-1", detected_ppe=None, required_ppe=["helmet", "vest"])
    assert result.ppe_violations == ["helmet", "vest"]
    assert result.ppe_compliance_score == 0.0


def test_unknown_ppe_key_is_reported_separately_not_as_a_violation():
    detected = {"helmet": True, "vest": True, "ear_protection": True}
    result = evaluate_ppe_compliance(worker_id="W-1", zone_id="Z-1", detected_ppe=detected, required_ppe=["helmet", "vest"])
    assert result.is_fully_compliant
    assert result.unknown_ppe_keys == ["ear_protection"]


def test_empty_required_ppe_is_vacuously_compliant():
    result = evaluate_ppe_compliance(worker_id="W-1", zone_id="Z-1", detected_ppe={}, required_ppe=[])
    assert result.is_fully_compliant
    assert result.ppe_compliance_score == 1.0
    assert result.ppe_violations == []


def test_payload_fragment_matches_frozen_field_names_and_types():
    result = evaluate_ppe_compliance(
        worker_id="W-1", zone_id="Z-1", detected_ppe=_full_detection(missing="gloves"), required_ppe=REAL_ITEMS
    )
    fragment = result.to_worker_analysis_payload_fragment()
    assert set(fragment.keys()) == {"ppe_compliance", "ppe_violations"}
    assert isinstance(fragment["ppe_compliance"], float)
    assert isinstance(fragment["ppe_violations"], list)
