from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import ClassVar
from uuid import UUID


class ConfidenceDerivation(str, Enum):
    RULE_BASED = "RULE_BASED"
    MODEL_BASED = "MODEL_BASED"
    COMPOSITE = "COMPOSITE"


class ConfidenceScore(BaseModel):
    """A structured confidence value with provenance, distinguishing rule-derived from model-derived confidence so downstream consumers never conflate the two."""
    value: float
    derivation: ConfidenceDerivation
    model_name: str | None = None
    model_version: str | None = None
    rule_id: str | None = None
    rule_version: int | None = None
