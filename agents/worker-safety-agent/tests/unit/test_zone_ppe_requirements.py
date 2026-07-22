import pytest

from zone_ppe_requirements import ZonePPERequirements
from config import build_zone_ppe_requirements


def test_default_applies_when_zone_has_no_override():
    reqs = ZonePPERequirements()
    assert reqs.required_for("Z-999") == ["helmet", "vest"]


def test_per_zone_override_wins():
    reqs = ZonePPERequirements(per_zone={"Z-104": ["helmet", "vest", "gloves"]})
    assert reqs.required_for("Z-104") == ["helmet", "vest", "gloves"]
    assert reqs.required_for("Z-999") == ["helmet", "vest"]  # unaffected


def test_build_zone_ppe_requirements_reads_env_var(monkeypatch):
    monkeypatch.setenv("WORKER_SAFETY_REQUIRED_PPE", '{"Z-104": ["helmet", "vest", "gloves"]}')
    reqs = build_zone_ppe_requirements()
    assert reqs.required_for("Z-104") == ["helmet", "vest", "gloves"]
    assert reqs.required_for("Z-201") == ["helmet", "vest"]


def test_build_zone_ppe_requirements_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("WORKER_SAFETY_REQUIRED_PPE", raising=False)
    reqs = build_zone_ppe_requirements()
    assert reqs.required_for("Z-1") == ["helmet", "vest"]


def test_build_zone_ppe_requirements_rejects_malformed_json(monkeypatch):
    from sentinel_common.errors import ConfigurationError

    monkeypatch.setenv("WORKER_SAFETY_REQUIRED_PPE", "not json")
    with pytest.raises(ConfigurationError):
        build_zone_ppe_requirements()
