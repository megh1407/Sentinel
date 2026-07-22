"""
Incident Model
"""

from dataclasses import dataclass


@dataclass
class Incident:

    incident_id: str

    incident_type: str

    zone_id: str

    severity: str

    description: str

    injuries: int = 0

    fatalities: int = 0