from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import ClassVar
from uuid import UUID


class Environment(str, Enum):
    DEV = "DEV"
    STAGING = "STAGING"
    PROD = "PROD"


class Metadata(BaseModel):
    """Envelope metadata attached to every event for schema governance, retry tracking, and audit correlation."""
    schema_id: int
    schema_version: int
    retry_count: int = 0
    audit_id: str | None = None
    environment: Environment
    tags: dict[str, str] = Field(default_factory=dict)
