"""
config.py

Layered configuration resolution for Zone Intelligence Agent (spec Part 13).
No sentinel_config package exists anywhere in this codebase yet (checked --
it isn't a gap specific to this agent), so this is a self-contained,
dependency-free resolver an eventual sentinel_config service could replace
without changing ZoneConfig's public interface (resolve()).

Precedence, most specific wins (spec lists five layers; this is the order
that makes operational sense -- an environment-wide override like "DEV mode,
relax everything" should be able to beat a single rule's default, but a
site-specific tuning should still beat a generic environment default):

    rule > site > agent > environment > global

Each layer is just a dict of overrides. A key not present at a more specific
layer falls through to the next. GLOBAL_DEFAULTS below preserves every
threshold this agent already used as hardcoded constants, so building this
resolver changes NOTHING about existing behavior unless a more specific
override is actually configured -- this is why all 26 pre-existing tests
keep passing unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Every value that was previously a bare module-level constant in
# zone_intelligence_agent.py, now the GLOBAL (least specific) layer.
GLOBAL_DEFAULTS: dict = {
    "worker_threshold": 10,                 # was MAX_OCCUPANCY_PER_ZONE
    "incident_count_threshold": 3,
    "incident_window_seconds": 24 * 60 * 60,
    "repeated_anomaly_threshold": 3,
    "repeated_anomaly_window_seconds": 60 * 60,
    "rapid_state_change_threshold": 8,
    "rapid_state_change_window_seconds": 5 * 60,
    "sensor_stale_seconds": 10 * 60,
    "conflicting_permit_type_pairs": frozenset({frozenset({"HOT_WORK", "CONFINED_SPACE"})}),
    "cache_ttl_seconds": 120,               # spec Part 13's "cache_ttl"; Redis TTL on live ZoneState
    # NOTE: gas_threshold / temperature_threshold / pressure_threshold, also named in
    # spec Part 13, are deliberately NOT here. SensorEventPayload already carries a
    # pre-computed threshold_breached boolean -- the raw-value-vs-threshold comparison
    # happens upstream (in whatever ingestion service produces SensorEvent), not in
    # Zone Intelligence Agent. Including unused keys here would misrepresent what this
    # agent actually controls.
}


@dataclass
class ZoneConfig:
    """Holds override layers and resolves a key through them, most specific
    first. All layer arguments are optional dicts; omit a layer entirely if
    it has no overrides for this deployment. This is intentionally NOT a
    singleton/global -- each agent instance builds its own, so tests can
    construct isolated configs without leaking state between them."""

    global_overrides: dict = field(default_factory=dict)
    environment_overrides: dict = field(default_factory=dict)
    agent_overrides: dict = field(default_factory=dict)
    site_overrides: dict = field(default_factory=dict)   # keyed by site_id -> {key: value}
    rule_overrides: dict = field(default_factory=dict)   # keyed by rule_id -> {key: value}

    def resolve(self, key: str, *, site_id: str | None = None, rule_id: str | None = None):
        """Most specific applicable layer wins. A layer that doesn't
        mention `key` is transparent -- resolution keeps falling through,
        it does NOT stop just because the layer itself exists."""
        if rule_id is not None and key in self.rule_overrides.get(rule_id, {}):
            return self.rule_overrides[rule_id][key]
        if site_id is not None and key in self.site_overrides.get(site_id, {}):
            return self.site_overrides[site_id][key]
        if key in self.agent_overrides:
            return self.agent_overrides[key]
        if key in self.environment_overrides:
            return self.environment_overrides[key]
        if key in self.global_overrides:
            return self.global_overrides[key]
        if key in GLOBAL_DEFAULTS:
            return GLOBAL_DEFAULTS[key]
        raise KeyError(f"no configured value or default for '{key}'")
