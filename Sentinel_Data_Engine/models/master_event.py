"""
Master Event

Internal object from which contract events are generated.
"""

from dataclasses import dataclass

from models.plant_state import PlantState
from models.worker import Worker
from models.machine import Machine
from models.sensor import Sensor
from models.permit import Permit
from models.risk import Risk


@dataclass
class MasterEvent:

    timestamp: str

    plant: PlantState

    worker: Worker

    machine: Machine

    sensor: Sensor

    permit: Permit | None

    risk: Risk