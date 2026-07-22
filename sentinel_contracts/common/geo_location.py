from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import ClassVar
from uuid import UUID


class GeoLocation(BaseModel):
    """Optional physical coordinate, used where a site's zone geometry requires a point reference (e.g. a specific sensor mount point within a zone polygon)."""
    latitude: float
    longitude: float
    elevation_meters: float | None = None
