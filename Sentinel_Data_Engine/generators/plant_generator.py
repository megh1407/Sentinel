"""
============================================================
Sentinel Data Engine

Plant Generator 2.0

Maintains correlated physical conditions
inside every plant zone.
============================================================
"""

import random

from config.constants import ZONES
from models.plant_state import PlantState


class PlantGenerator:

    def __init__(self):

        self.zones = {}

        self.initialize()

    # =====================================================

    def initialize(self):

        for zone in ZONES:

            state = PlantState(zone_id=zone)

            state.temperature = random.uniform(24, 30)
            state.humidity = random.uniform(40, 60)
            state.pressure = 1.00
            state.gas_ppm = random.uniform(5, 20)

            state.machine_temperature = random.uniform(35, 45)
            state.vibration = random.uniform(0.10, 0.30)

            state.smoke = False
            state.flame = False

            state.scenario = "NORMAL_OPERATION"

            self.zones[zone] = state

    # =====================================================

    def get_zone(self, zone):

        return self.zones[zone]

    # =====================================================

    def all_zones(self):

        return list(self.zones.values())

    # =====================================================

    def update(self, scenario):

        for zone in self.zones.values():

            zone.scenario = scenario.name

            # ------------------------------------------------
            # Natural Drift
            # ------------------------------------------------

            zone.temperature += random.uniform(-0.15, 0.15)

            zone.humidity += random.uniform(-0.30, 0.30)

            zone.pressure += random.uniform(-0.003, 0.003)

            zone.machine_temperature += random.uniform(-0.25, 0.25)

            zone.vibration += random.uniform(-0.01, 0.01)

            # ------------------------------------------------
            # Scenario Physics
            # ------------------------------------------------

            if scenario.name == "HOT_WORK":

                zone.temperature += 1.2
                zone.machine_temperature += 2.0

            elif scenario.name == "MAINTENANCE":

                zone.machine_temperature -= 1.5
                zone.vibration -= 0.03

            elif scenario.name == "GAS_LEAK":

                zone.gas_ppm += random.uniform(40, 80)

                if zone.gas_ppm > 250:
                    zone.smoke = True

            elif scenario.name == "FIRE":

                zone.temperature += 8
                zone.machine_temperature += 12

                zone.gas_ppm += 120

                zone.smoke = True
                zone.flame = True

            elif scenario.name == "EQUIPMENT_FAILURE":

                zone.machine_temperature += 8
                zone.vibration += 0.6

            elif scenario.name == "EXPLOSION":

                zone.temperature = 95
                zone.machine_temperature = 120

                zone.gas_ppm = 1000

                zone.pressure = 1.08

                zone.smoke = True
                zone.flame = True

            elif scenario.name == "NORMAL_OPERATION":

                zone.gas_ppm *= 0.97

                if zone.gas_ppm < 40:

                    zone.smoke = False
                    zone.flame = False

            # ------------------------------------------------
            # Clamp Values
            # ------------------------------------------------

            zone.temperature = max(20, min(100, zone.temperature))

            zone.humidity = max(20, min(100, zone.humidity))

            zone.pressure = max(0.95, min(1.08, zone.pressure))

            zone.gas_ppm = max(0, min(1000, zone.gas_ppm))

            zone.machine_temperature = max(

                25,

                min(130, zone.machine_temperature)

            )

            zone.vibration = max(

                0,

                min(5, zone.vibration)

            )

    # =====================================================

    def snapshot(self):

        return {

            zone.zone_id: {

                "scenario": zone.scenario,

                "temperature": round(zone.temperature, 2),

                "humidity": round(zone.humidity, 2),

                "pressure": round(zone.pressure, 3),

                "gas_ppm": round(zone.gas_ppm, 2),

                "machine_temperature": round(

                    zone.machine_temperature,

                    2

                ),

                "vibration": round(

                    zone.vibration,

                    3

                ),

                "smoke": zone.smoke,

                "flame": zone.flame

            }

            for zone in self.zones.values()

        }