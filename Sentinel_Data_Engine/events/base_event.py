"""
============================================================
Sentinel Data Engine

Base Event
Implements the official SENTINEL BaseEvent contract.
============================================================
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class BaseEvent:

    # ======================================================
    # Required Contract Fields
    # ======================================================

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

    # ======================================================

    def to_dict(self):

        return asdict(self)

    # ======================================================

    def to_json(self):

        import json

        return json.dumps(

            self.to_dict(),

            indent=4

        )