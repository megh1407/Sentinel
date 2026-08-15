"""
sensor_snapshot_aggregator.py

WHY THIS FILE EXISTS: engine/*.py (the preserved, frozen business logic)
expects a single call carrying a full multi-reading snapshot -- methane,
carbon_monoxide, hydrogen_sulfide, oxygen, voc, ammonia, temperature,
humidity, pressure all at once (see the constructor signatures throughout
engine/threshold_service.py, engine/risk_service.py, etc., all of which
were written against that shape and are NOT being changed). The platform's
event bus delivers one SensorEvent per reading instead. This module is the
integration-layer adapter that buffers readings until a snapshot is
available -- it contains no threshold/risk/detection logic of its own; it
only reshapes data before handing it to the engine.

BLOCKED: B3 (see migration report). sentinel_contracts.events.sensor_event_v1
.SensorType has exactly one GAS value -- there is no field anywhere on
SensorEventPayload that says whether a given GAS reading is methane, CO,
H2S, O2, VOC, or NH3. This class can therefore only populate the
non-gas fields of a snapshot (temperature, humidity, pressure) from real
SensorEvent traffic today. Every GAS reading is counted and logged, never
guessed at or dropped silently. Wiring the gas fields in is a small change
to _SENSOR_TYPE_TO_FIELD once B3 is resolved -- see EnvironmentalConfig's
and this class's docstrings for what "resolved" means here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sentinel_contracts.events.sensor_event_v1 import SensorEventV1, SensorType


@dataclass
class PartialSnapshot:
    """Accumulates readings for one (site_id, zone_id) pair. Field names
    intentionally match the keyword arguments engine/threshold_service.py's
    ThresholdService.check_all_thresholds() and the other engine entry
    points already expect, so that once B3 unblocks the gas fields, wiring
    this into the engine is a dict-unpack, not a rewrite."""
    site_id: str
    zone_id: str
    readings: dict[str, float] = field(default_factory=dict)   # e.g. {"temperature": 41.2, "methane": 900.0}
    gas_sensor_ids: dict[str, str] = field(default_factory=dict)  # species -> originating sensor_id
    dropped_gas_readings: int = 0                                # only unrecognized/untagged GAS readings

    @property
    def known_fields(self) -> frozenset[str]:
        return frozenset(self.readings.keys())


class SensorSnapshotAggregator:
    """Buffers SensorEventV1 readings per zone. Non-gas sensor types map
    directly onto engine input field names; GAS is intentionally excluded
    from the map until B3 is resolved (see module docstring) rather than
    mapped to a guessed field name."""

    _SENSOR_TYPE_TO_ENGINE_FIELD: dict[SensorType, str] = {
        SensorType.TEMPERATURE: "temperature",
        SensorType.HUMIDITY: "humidity",
        SensorType.PRESSURE: "pressure",
        # SensorType.GAS is resolved dynamically from payload.raw_metadata
        # ["gas_species"] below (B3), not via this static map.
    }

    # B3 RESOLVED: SensorType has a single undifferentiated GAS value, but the
    # canonical SensorEventPayload already carries a free-form
    # `raw_metadata: dict[str,str]` extensibility field. Producers tag each gas
    # reading with `gas_species` (see scripts/demo/run_demo.py._gas_event); we
    # accept the six species ThresholdService already has configured thresholds
    # for, using the species name directly as the engine input field name (the
    # engine services -- threshold_service._get_thresholds_for_gas etc. -- key
    # on exactly these names). An untagged or unrecognized species is still
    # counted and dropped, never guessed at.
    _RECOGNIZED_GAS_SPECIES: frozenset[str] = frozenset(
        {"methane", "carbon_monoxide", "hydrogen_sulfide", "oxygen", "voc", "ammonia"}
    )

    def __init__(self) -> None:
        self._buffers: dict[tuple[str, str], PartialSnapshot] = {}

    def clear_all(self) -> None:
        """Demo/test-only: wipes every zone's accumulated reading buffer at
        once. Distinct from clear(site_id, zone_id) above (per-zone, used
        mid-pipeline) -- without this, buffers from a previous scenario
        silently bleed into the next one across ALL zones."""
        self._buffers.clear()

    def ingest(self, event: SensorEventV1) -> PartialSnapshot:
        """Folds one SensorEvent into its zone's running snapshot and
        returns the (still-partial, until B3) snapshot for that zone."""
        key = (event.site_id, event.zone_id)
        snapshot = self._buffers.get(key)
        if snapshot is None:
            snapshot = PartialSnapshot(site_id=event.site_id, zone_id=event.zone_id)
            self._buffers[key] = snapshot

        engine_field = self._SENSOR_TYPE_TO_ENGINE_FIELD.get(event.payload.sensor_type)
        if engine_field is not None:
            snapshot.readings[engine_field] = event.payload.value
        elif event.payload.sensor_type == SensorType.GAS:
            species = (event.payload.raw_metadata or {}).get("gas_species")
            if species in self._RECOGNIZED_GAS_SPECIES:
                snapshot.readings[species] = event.payload.value
                snapshot.gas_sensor_ids[species] = event.payload.sensor_id
            else:
                snapshot.dropped_gas_readings += 1

        return snapshot

    def clear(self, site_id: str, zone_id: str) -> None:
        """Optional reset hook (e.g. after a snapshot has been consumed by
        the engine and a fresh one should start accumulating). Not called
        anywhere yet -- process() doesn't run the engine yet either, see
        environmental_intelligence_agent.py."""
        self._buffers.pop((site_id, zone_id), None)
