"""
============================================================
Sentinel Data Engine

Generic Contract Event

Every SENTINEL event is created from this class.
============================================================
"""

from dataclasses import dataclass, field, asdict
from uuid import uuid4
from datetime import datetime, timezone
import json


@dataclass
class ContractEvent:

    # =====================================================
    # Base Contract
    # =====================================================

    event_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    event_type: str = ""

    event_version: int = 1

    timestamp: str = field(
        default_factory=lambda:
        datetime.now(timezone.utc).isoformat()
    )

    source: str = "Sentinel_Data_Engine"

    site_id: str = ""

    zone_id: str = ""

    correlation_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    causation_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    schema_version: str = "v1"

    # =====================================================
    # Event Payload
    # =====================================================

    payload: dict = field(
        default_factory=dict
    )

    metadata: dict = field(
        default_factory=dict
    )

    # =====================================================

    def set_payload(self, payload: dict):

        self.payload = payload

        return self

    # =====================================================

    def set_metadata(self, metadata: dict):

        self.metadata = metadata

        return self

    # =====================================================

    def to_dict(self):

        return asdict(self)

    # =====================================================

    def to_json(self):

        return json.dumps(

            self.to_dict(),

            indent=4

        )

    # =====================================================

    def copy(self):

        return ContractEvent(

            event_type=self.event_type,

            event_version=self.event_version,

            source=self.source,

            site_id=self.site_id,

            zone_id=self.zone_id,

            correlation_id=self.correlation_id,

            causation_id=self.causation_id,

            schema_version=self.schema_version,

            payload=self.payload.copy(),

            metadata=self.metadata.copy()

        )