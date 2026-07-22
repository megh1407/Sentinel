"""
============================================================
Sentinel Data Engine

Environment Generator

Generates EnvironmentalEvent objects from
aggregated plant conditions.
============================================================
"""

import random

from events.environmental_event import EnvironmentalEvent


class EnvironmentGenerator:

    def __init__(self):

        self.wind = [

            "N",

            "NE",

            "E",

            "SE",

            "S",

            "SW",

            "W",

            "NW"

        ]

    # =====================================================

    def generate(

        self,

        site_id,

        plant_state

    ):

        gas = plant_state.gas_ppm

        if gas < 200:

            severity = "normal"

        elif gas < 400:

            severity = "elevated"

        elif gas < 700:

            severity = "warning"

        else:

            severity = "critical"

        readings = [

            {

                "sensor_id": f"{plant_state.zone_id}_GAS",

                "value": gas,

                "unit": "ppm"

            },

            {

                "sensor_id": f"{plant_state.zone_id}_TEMP",

                "value": plant_state.temperature,

                "unit": "°C"

            }

        ]

        event = EnvironmentalEvent(

            site_id=site_id,

            zone_id=plant_state.zone_id

        )

        event.set_environment_data(

            event_type="env.condition_change",

            condition_type="chemical_concentration",

            severity=severity,

            affected_area_m2=random.randint(

                25,

                500

            ),

            wind_direction=random.choice(

                self.wind

            ),

            wind_speed_ms=round(

                random.uniform(

                    1,

                    10

                ),

                2

            ),

            dispersion_model="GAUSSIAN_PLUME",

            predicted_spread={

                "type": "Polygon",

                "coordinates": []

            },

            readings=readings,

            regulatory_limit=100,

            measured_value=gas,

            exceedance_factor=round(

                gas / 100,

                2

            )

        )

        return event