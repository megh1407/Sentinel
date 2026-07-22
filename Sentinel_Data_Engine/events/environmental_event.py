"""
============================================================
Sentinel Data Engine

Environmental Event
============================================================
"""

from dataclasses import dataclass

from events.contract_event import ContractEvent


@dataclass
class EnvironmentalEvent(ContractEvent):

    def __post_init__(self):

        self.event_type = "env.condition_change"

    def set_environment_data(

        self,

        event_type,

        condition_type,

        severity,

        affected_area_m2,

        wind_direction,

        wind_speed_ms,

        dispersion_model,

        predicted_spread,

        readings,

        regulatory_limit,

        measured_value,

        exceedance_factor

    ):

        self.event_type = event_type

        self.payload = {

            "condition_type": condition_type,

            "severity": severity,

            "affected_area_m2": affected_area_m2,

            "wind_direction": wind_direction,

            "wind_speed_ms": wind_speed_ms,

            "dispersion_model": dispersion_model,

            "predicted_spread": predicted_spread,

            "readings": readings,

            "regulatory_limit": regulatory_limit,

            "measured_value": measured_value,

            "exceedance_factor": exceedance_factor

        }

        return self