"""
============================================================
Sentinel Data Engine

Incident Generator 2.0

Creates realistic industrial incident chains.
============================================================
"""

import random
from uuid import uuid4

from events.incident_event import IncidentEvent


class IncidentGenerator:

    CHAINS = {

        "NORMAL_OPERATION": [],

        "HOT_WORK": [

            ("permit.created", None),

            ("permit.activated", None),

            ("incident.near_miss", "near_miss")

        ],

        "MAINTENANCE": [

            ("incident.reported", "equipment_failure")

        ],

        "GAS_LEAK": [

            ("incident.reported", "gas_leak"),

            ("incident.updated", "gas_leak")

        ],

        "FIRE": [

            ("incident.reported", "fire"),

            ("incident.updated", "fire"),

            ("incident.investigation_complete", "fire")

        ],

        "EXPLOSION": [

            ("incident.reported", "explosion"),

            ("incident.updated", "explosion"),

            ("incident.investigation_complete", "explosion"),

            ("incident.closed", "explosion")

        ],

        "EQUIPMENT_FAILURE": [

            ("incident.reported", "equipment_failure"),

            ("incident.updated", "equipment_failure")

        ]

    }

    SEVERITY = {

        "near_miss": "minor",

        "equipment_failure": "moderate",

        "gas_leak": "major",

        "fire": "critical",

        "explosion": "catastrophic"

    }

    # =====================================================

    def generate(

        self,

        site_id,

        zone_id,

        scenario

    ):

        if scenario.name == "NORMAL_OPERATION":

            return None

        chain = self.CHAINS.get(

            scenario.name,

            []

        )

        if not chain:

            return None

        event_type, incident_type = random.choice(chain)

        if incident_type is None:

            return None

        event = IncidentEvent(

            site_id=site_id,

            zone_id=zone_id

        )

        severity = self.SEVERITY[incident_type]

        event.set_incident_data(

            event_type=event_type,

            incident_id=str(uuid4()),

            incident_type=incident_type,

            severity=severity,

            description=f"{incident_type.replace('_',' ').title()} detected in {zone_id}.",

            root_cause=scenario.name,

            contributing_factors=[

                scenario.name,

                "Sensor Correlation",

                "Automatic Detection"

            ],

            injuries=0 if severity in [

                "minor",

                "moderate"

            ] else random.randint(1,3),

            fatalities=1 if severity=="catastrophic" else 0,

            remediation_taken=[

                "Emergency Shutdown",

                "Area Isolation",

                "Emergency Response"

            ],

            regulatory_report_required=severity in [

                "critical",

                "catastrophic"

            ],

            regulatory_reference="OSHA-1910",

            investigation_findings="Automatically generated incident chain."

        )

        return event