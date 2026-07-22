"""
============================================================
Sentinel Data Engine

Action Result Event

Official implementation of the ActionResult
contract.
============================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class ActionResultEvent:

    # =====================================================
    # Event Header
    # =====================================================

    event_id: str = field(default_factory=lambda: str(uuid4()))

    event_type: str = "ActionResult"

    event_version: int = 1

    event_timestamp: int = field(
        default_factory=lambda: int(
            datetime.now(
                timezone.utc
            ).timestamp() * 1000
        )
    )

    correlation_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    causation_id: str | None = None

    producer_service: str = "ActionPolicyGateway"

    producer_version: str = "1.0.0"

    site_id: str = ""

    zone_id: str | None = None

    partition_key: str = ""

    trace_id: str | None = None

    # =====================================================
    # Metadata
    # =====================================================

    metadata: dict = field(default_factory=dict)

    payload: dict = field(default_factory=dict)

    # =====================================================

    def set_action_result(

        self,

        action_id: str,

        outcome: str,

        approved_by: str | None = None,

        executed_at: int | None = None,

        failure_reason: str | None = None,

        downstream_confirmation: str | None = None

    ):

        self.partition_key = action_id

        self.payload = {

            "action_id": action_id,

            "outcome": outcome,

            "approved_by": approved_by,

            "executed_at": executed_at,

            "failure_reason": failure_reason,

            "downstream_confirmation": downstream_confirmation

        }

    # =====================================================

    def to_dict(self):

        return {

            "event_id": self.event_id,

            "event_type": self.event_type,

            "event_version": self.event_version,

            "event_timestamp": self.event_timestamp,

            "correlation_id": self.correlation_id,

            "causation_id": self.causation_id,

            "producer_service": self.producer_service,

            "producer_version": self.producer_version,

            "site_id": self.site_id,

            "zone_id": self.zone_id,

            "partition_key": self.partition_key,

            "trace_id": self.trace_id,

            "metadata": self.metadata,

            "payload": self.payload

        }