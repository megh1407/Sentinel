"""
config.py

Layered configuration for Environmental Intelligence Agent, following
zone_intelligence_agent/config.py's established pattern (rule > site >
agent > environment > global, most-specific-wins -- see that file for the
canonical version of this pattern in this repository).

WHY THIS FILE EXISTS: the standalone gas-intelligence-agent's
app/config.py was a pydantic-settings BaseSettings class mixing genuine
business constants (thresholds, weights, prediction parameters) with
platform-integration concerns that don't belong in an agent's own config
anymore (Kafka bootstrap servers, direct HTTP URLs to other agents,
database DSNs) -- see the migration report for why those were dropped
outright rather than migrated.

GLOBAL_DEFAULTS below is a byte-for-byte value migration of every
threshold/weight/prediction/history constant that used to live in
Settings. No number was changed, added, or removed.

`settings`, at the bottom of this file, exists ONLY so that
threshold_service.py and prediction_service.py -- two of the frozen,
preserved business-logic files -- can keep their existing
`settings.THRESHOLD_METHANE_PPM` / `getattr(settings, config_key, None)`
call sites completely unmodified. This is a configuration-loading change
(explicitly an allowed modification), not a business-logic change: those
two files are not aware that the values now flow through
EnvironmentalConfig.resolve() underneath.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

GLOBAL_DEFAULTS: dict = {
    # Gas concentration thresholds (ppm unless noted), migrated verbatim
    # from the standalone service's app/config.py Settings class.
    "THRESHOLD_METHANE_PPM": 1000.0,
    "THRESHOLD_CARBON_MONOXIDE_PPM": 35.0,
    "THRESHOLD_HYDROGEN_SULFIDE_PPM": 10.0,
    "THRESHOLD_OXYGEN_PERCENT": 19.5,
    "THRESHOLD_VOC_PPM": 500.0,
    "THRESHOLD_AMMONIA_PPM": 25.0,
    "THRESHOLD_TEMPERATURE_CELSIUS": 50.0,
    "THRESHOLD_HUMIDITY_PERCENT": 90.0,
    "THRESHOLD_PRESSURE_PSI": 100.0,
    # Risk scoring weights. NOTE: these were dead configuration in the
    # original service too -- risk_service.py has always used its own
    # internal hardcoded weight dict (see migration report, §4.3-adjacent
    # finding) rather than reading these. Preserved here anyway, unused,
    # for parity with the original Settings class and in case a future
    # (non-frozen) change wires risk_service.py up to them.
    "WEIGHT_METHANE": 0.20,
    "WEIGHT_CARBON_MONOXIDE": 0.20,
    "WEIGHT_HYDROGEN_SULFIDE": 0.15,
    "WEIGHT_OXYGEN": 0.10,
    "WEIGHT_VOC": 0.10,
    "WEIGHT_AMMONIA": 0.10,
    "WEIGHT_TEMPERATURE": 0.05,
    "WEIGHT_HUMIDITY": 0.05,
    "WEIGHT_PRESSURE": 0.05,
    # Prediction parameters, migrated verbatim.
    "PREDICTION_WINDOW_SIZE": 10,
    "PREDICTION_HORIZON": 5,
    "PREDICTION_CONFIDENCE_THRESHOLD": 0.7,
    # History management, migrated verbatim. Still governs
    # engine/history_manager.py's in-memory buffer -- see that file's
    # docstring for why it isn't backed by sentinel_state yet.
    "MAX_HISTORY_SIZE": 1000,
    "HISTORY_RETENTION_DAYS": 30,
}


@dataclass
class EnvironmentalConfig:
    """Layered resolver. Same shape as zone_intelligence_agent's config
    pattern: each layer is an optional dict of overrides, most specific
    wins, falls back to GLOBAL_DEFAULTS. No rule/site/agent/environment
    override source is wired up yet (no such config-loading mechanism was
    found elsewhere in the repository to reuse for this agent specifically
    -- see migration report's cross-check notes); all four override layers
    default to empty, which means resolve() currently always returns
    GLOBAL_DEFAULTS values. That's a deliberate, honest default: nothing
    here invents a rule-config source the platform doesn't actually give
    this agent yet.
    """
    global_overrides: dict = field(default_factory=dict)
    environment_overrides: dict = field(default_factory=dict)
    agent_overrides: dict = field(default_factory=dict)
    site_overrides: dict = field(default_factory=dict)
    rule_overrides: dict = field(default_factory=dict)

    def resolve(self, key: str):
        for layer in (self.rule_overrides, self.site_overrides, self.agent_overrides,
                      self.environment_overrides, self.global_overrides):
            if key in layer:
                return layer[key]
        return GLOBAL_DEFAULTS[key]

    def as_settings_namespace(self) -> SimpleNamespace:
        """Builds the flat attribute-access object threshold_service.py and
        prediction_service.py already expect (`settings.THRESHOLD_*`,
        `getattr(settings, key, None)`). Every key in GLOBAL_DEFAULTS is
        resolved through the same layered lookup as everything else --
        this is purely an adapter shape, not a second source of truth."""
        return SimpleNamespace(**{key: self.resolve(key) for key in GLOBAL_DEFAULTS})


# Module-level singleton, matching the import-time `from config import
# settings` call sites in threshold_service.py / prediction_service.py.
# Built from an EnvironmentalConfig with no overrides configured yet (see
# EnvironmentalConfig docstring) -- functionally identical to the original
# Settings() defaults for every key those two files actually read.
settings = EnvironmentalConfig().as_settings_namespace()
