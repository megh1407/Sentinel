"""
Plant State

Represents the current state of one industrial zone.
"""

from dataclasses import dataclass


@dataclass
class PlantState:

    zone_id: str

    scenario: str = "NORMAL"

    gas_ppm: float = 120.0

    temperature: float = 30.0

    humidity: float = 55.0

    pressure: float = 1.00

    smoke: bool = False

    flame: bool = False

    vibration: float = 0.20

    machine_temperature: float = 35.0

    current: float = 10.0

    voltage: float = 230.0

    occupancy: int = 0