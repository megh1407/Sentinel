"""
============================================================
Sentinel Data Engine

Event Factory

Creates contract-compliant events from internal models.
============================================================
"""

from events.contract_event import ContractEvent


class EventFactory:

    def __init__(self, source="Sentinel_Data_Engine"):

        self.source = source

    # -----------------------------------------------------

    def create(
        self,
        event_type: str,
        site_id: str,
        zone_id: str,
        payload: dict,
        metadata: dict | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        event_version: int = 1,
        schema_version: str = "v1",
    ) -> ContractEvent:

        event = ContractEvent()

        event.event_type = event_type

        event.event_version = event_version

        event.source = self.source

        event.site_id = site_id

        event.zone_id = zone_id

        event.schema_version = schema_version

        if correlation_id:
            event.correlation_id = correlation_id

        if causation_id:
            event.causation_id = causation_id

        event.set_payload(payload)

        event.set_metadata(metadata or {})

        return event

    # -----------------------------------------------------

    def clone(self, event: ContractEvent) -> ContractEvent:

        return event.copy()