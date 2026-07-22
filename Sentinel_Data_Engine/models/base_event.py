"""
============================================================
Sentinel Data Engine
Base Event Model
============================================================
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class BaseEvent:

    event_id: str = field(default_factory=lambda: str(uuid4()))

    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    causation_id: str | None = None

    event_type: str = ""

    source: str = "Sentinel_Data_Engine"

    schema_version: str = "v1"

    timestamp: str = field(
        default_factory=lambda:
        datetime.now(timezone.utc).isoformat()
    )

    site_id: str = ""

    zone_id: str = ""

    def to_dict(self):

        return asdict(self)