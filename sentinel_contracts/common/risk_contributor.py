from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import ClassVar
from uuid import UUID


class RiskContributor(BaseModel):
    """The concrete application of a named RiskFactor to a specific RiskScore, with its evidence pointer."""
    factor_name: str
    contribution_score: float
    description: str
    source_event_id: str | None = None
