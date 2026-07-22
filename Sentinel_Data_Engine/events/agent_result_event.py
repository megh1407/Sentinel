"""
============================================================
Sentinel Data Engine

Agent Result Event

Official AgentResult implementation.
============================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class AgentResultEvent:

    event_id: str = field(default_factory=lambda: str(uuid4()))

    event_type: str = "AgentResult"

    event_version: int = 1

    event_timestamp: int = field(
        default_factory=lambda: int(
            datetime.now(
                timezone.utc
            ).timestamp() * 1000
        )
    )

    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    causation_id: str | None = None

    producer_service: str = "Sentinel_AI"

    producer_version: str = "1.0.0"

    site_id: str = ""

    zone_id: str | None = None

    partition_key: str = ""

    trace_id: str | None = None

    metadata: dict = field(default_factory=dict)

    explanation: dict = field(default_factory=dict)

    payload: dict = field(default_factory=dict)

    def to_dict(self):

        return self.__dict__