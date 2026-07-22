"""
Machine Model
"""

from dataclasses import dataclass


@dataclass
class Machine:

    machine_id: str

    machine_name: str

    zone_id: str

    rpm: int

    vibration: float

    temperature: float

    pressure: float

    current: float

    voltage: float

    health: float = 100.0

    status: str = "Running"