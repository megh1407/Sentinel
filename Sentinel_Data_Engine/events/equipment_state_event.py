"""
============================================================
Sentinel Data Engine

Equipment State Event
============================================================
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from events.contract_event import ContractEvent


@dataclass
class EquipmentStateEvent(ContractEvent):

    def __post_init__(self):

        self.event_type = "equipment.state_change"

    def set_equipment_data(

        self,

        equipment_id: str,

        equipment_type: str,

        state: str,

        previous_state: str,

        health_index: float,

        active_faults=None,

        loto_reference="",

        isolation_authority=""

    ):

        if active_faults is None:

            active_faults = []

        self.payload = {

            "equipment_id": equipment_id,

            "equipment_type": equipment_type,

            "state": state,

            "previous_state": previous_state,

            "health_index": round(health_index,3),

            "active_faults": active_faults,

            "loto_reference": loto_reference,

            "isolation_authority": isolation_authority,

            "changed_at": datetime.now(

                timezone.utc

            ).isoformat()

        }

        return self