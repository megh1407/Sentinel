"""
Permit Model
"""

from dataclasses import dataclass


@dataclass
class Permit:

    permit_id: str

    worker_id: str

    permit_type: str

    zone_id: str

    valid: bool = True