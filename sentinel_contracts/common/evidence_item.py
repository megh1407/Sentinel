from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import ClassVar
from uuid import UUID


class EvidenceItem(BaseModel):
    """A single, pointer-based piece of evidence supporting an Explanation. Always traces back to a real, immutable, already-published source event -- never a synthesized or paraphrased fact."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['timestamp']
    source_event_id: str
    source_type: str
    description: str
    weight: float
    timestamp: datetime
