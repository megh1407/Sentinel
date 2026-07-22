"""
============================================================
Sentinel Data Engine

Worker Event
Implements the official WorkerEvent contract.
============================================================
"""

from dataclasses import dataclass
from events.contract_event import ContractEvent


@dataclass
class WorkerEvent(ContractEvent):

    def __post_init__(self):

        self.event_type = "worker.location"

    def set_worker_data(

        self,

        event_type,

        worker_id,

        role,

        contractor,

        location,

        ppe_status,

        biometrics,

        certifications

    ):

        self.event_type = event_type

        self.payload = {

            "worker_id": worker_id,

            "event_subtype": event_type.split(".")[1],

            "role": role,

            "contractor": contractor,

            "location": location,

            "ppe_status": ppe_status,

            "biometrics": biometrics,

            "certifications": certifications

        }

        return self