"""
============================================================
Sentinel Data Engine

Machine Generator 2.0

Lifecycle-based equipment simulation.
============================================================
"""

import random
from uuid import uuid4

from events.equipment_state_event import EquipmentStateEvent


class MachineGenerator:

    MACHINE_TYPES = [

        "Pump",
        "Motor",
        "Compressor",
        "Boiler",
        "CoolingTower",
        "Conveyor"

    ]

    def __init__(self, total=20):

        self.machines = []

        for i in range(total):

            self.machines.append({

                "equipment_id": str(uuid4()),

                "equipment_type": random.choice(

                    self.MACHINE_TYPES

                ),

                "state": "operational",

                "previous_state": "operational",

                "health": 1.0

            })

    # =====================================================

    def update(self):

        for machine in self.machines:

            machine["previous_state"] = machine["state"]

            machine["health"] -= random.uniform(

                0.0005,

                0.005

            )

            machine["health"] = max(

                machine["health"],

                0

            )

            h = machine["health"]

            if h > 0.85:

                machine["state"] = "operational"

            elif h > 0.65:

                machine["state"] = "degraded"

            elif h > 0.40:

                machine["state"] = "fault"

            elif h > 0.20:

                machine["state"] = "isolated"

            else:

                machine["state"] = "maintenance"

            if (

                machine["state"] == "maintenance"

                and random.random() < 0.10

            ):

                machine["health"] = 1.0

                machine["previous_state"] = "maintenance"

                machine["state"] = "operational"

    # =====================================================

    def generate_events(

        self,

        site_id,

        zone_id

    ):

        events = []

        for machine in self.machines:

            faults = []

            if machine["state"] == "fault":

                faults.append("Bearing Wear")

            elif machine["state"] == "isolated":

                faults.append("Emergency Isolation")

            elif machine["state"] == "maintenance":

                faults.append("Scheduled Maintenance")

            event = EquipmentStateEvent(

                site_id=site_id,

                zone_id=zone_id

            )

            event.set_equipment_data(

                equipment_id=machine["equipment_id"],

                equipment_type=machine["equipment_type"],

                state=machine["state"],

                previous_state=machine["previous_state"],

                health_index=round(

                    machine["health"],

                    3

                ),

                active_faults=faults

            )

            events.append(event)

        return events