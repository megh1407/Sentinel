"""
Sensor Model
"""

from dataclasses import dataclass


@dataclass
class Sensor:

    sensor_id: str

    zone_id: str

    gas_ppm: float

    temperature: float

    humidity: float

    pressure: float

    smoke: bool

    flame: bool