"""
============================================================
Sentinel Data Engine

Sensor Generator 2.0

Generates realistic correlated sensor readings
from the current plant state.
============================================================
"""

import random

from events.sensor_event import SensorEvent


class SensorGenerator:

    SENSOR_MAP = {

        "gas_ppm": {

            "type": "Gas Sensor",

            "unit": "ppm"

        },

        "temperature": {

            "type": "Temperature Sensor",

            "unit": "°C"

        },

        "humidity": {

            "type": "Humidity Sensor",

            "unit": "%"

        },

        "pressure": {

            "type": "Pressure Sensor",

            "unit": "bar"

        },

        "machine_temperature": {

            "type": "Machine Temperature",

            "unit": "°C"

        },

        "vibration": {

            "type": "Vibration Sensor",

            "unit": "mm/s"

        }

    }

    # =====================================================

    def __init__(self):

        pass

    # =====================================================

    def _noise(self, value):

        if isinstance(value, bool):

            return value

        noise = value * 0.02

        return round(

            value +

            random.uniform(-noise, noise),

            2

        )

    # =====================================================

    def _status(self, sensor, value):

        if sensor == "gas_ppm":

            if value < 50:

                return "Normal"

            elif value < 200:

                return "Warning"

            return "Critical"

        if sensor == "temperature":

            if value < 40:

                return "Normal"

            elif value < 60:

                return "Warning"

            return "Critical"

        if sensor == "machine_temperature":

            if value < 70:

                return "Normal"

            elif value < 90:

                return "Warning"

            return "Critical"

        if sensor == "vibration":

            if value < 1.5:

                return "Normal"

            elif value < 3:

                return "Warning"

            return "Critical"

        return "Normal"

    # =====================================================

    def generate(

        self,

        site_id,

        plant_state

    ):

        events = []

        for sensor_name, info in self.SENSOR_MAP.items():

            raw_value = getattr(

                plant_state,

                sensor_name

            )

            value = self._noise(

                raw_value

            )

            status = self._status(

                sensor_name,

                value

            )

            event = SensorEvent(

                site_id=site_id,

                zone_id=plant_state.zone_id

            )

            event.set_sensor_data(

                sensor_id=f"{plant_state.zone_id}_{sensor_name.upper()}",

                sensor_type=info["type"],

                value=value,

                unit=info["unit"],

                status=status

            )

            events.append(

                event

            )

        # ------------------------------------------
        # Smoke Detector
        # ------------------------------------------

        smoke = SensorEvent(

            site_id=site_id,

            zone_id=plant_state.zone_id

        )

        smoke.set_sensor_data(

            sensor_id=f"{plant_state.zone_id}_SMOKE",

            sensor_type="Smoke Detector",

            value=int(

                plant_state.smoke

            ),

            unit="bool",

            status="Critical"

            if plant_state.smoke

            else "Normal"

        )

        events.append(

            smoke

        )

        # ------------------------------------------
        # Flame Detector
        # ------------------------------------------

        flame = SensorEvent(

            site_id=site_id,

            zone_id=plant_state.zone_id

        )

        flame.set_sensor_data(

            sensor_id=f"{plant_state.zone_id}_FLAME",

            sensor_type="Flame Detector",

            value=int(

                plant_state.flame

            ),

            unit="bool",

            status="Critical"

            if plant_state.flame

            else "Normal"

        )

        events.append(

            flame

        )

        return events