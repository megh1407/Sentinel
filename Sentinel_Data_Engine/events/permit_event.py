"""
============================================================
Sentinel Data Engine

Permit Event

Implements the official PermitEvent contract.
============================================================
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from events.contract_event import ContractEvent


@dataclass
class PermitEvent(ContractEvent):

    def __post_init__(self):

        self.event_type = "permit.created"

    def set_permit_data(

        self,

        event_type,

        permit_id,

        permit_type,

        lifecycle_status,

        issued_to,

        issued_by,

        valid_from,

        valid_until,

        zone_restrictions,

        concurrent_permits,

        conditions,

        gas_test_required,

        isolation_points

    ):

        self.event_type = event_type

        self.payload = {

            "permit_id": permit_id,

            "permit_type": permit_type,

            "lifecycle_status": lifecycle_status,

            "issued_to": issued_to,

            "issued_by": issued_by,

            "valid_from": valid_from,

            "valid_until": valid_until,

            "zone_restrictions": zone_restrictions,

            "concurrent_permits": concurrent_permits,

            "conditions": conditions,

            "gas_test_required": gas_test_required,

            "isolation_points": isolation_points

        }

        return self