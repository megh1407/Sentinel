"""
Sensor Event
"""

from dataclasses import dataclass

from events.contract_event import ContractEvent


@dataclass
class SensorEvent(ContractEvent):

    def __post_init__(self):

        self.event_type = "sensor.reading"

    def set_sensor_data(
        self,
        sensor_id: str,
        sensor_type: str,
        value: float,
        unit: str,
        status: str
    ):

        self.payload = {

            "sensor_id": sensor_id,

            "sensor_type": sensor_type,

            "value": value,

            "unit": unit,

            "status": status

        }

        return self