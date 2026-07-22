"""
Worker Model
"""

from dataclasses import dataclass


@dataclass
class Worker:

    worker_id: str

    full_name: str

    role: str

    zone_id: str

    shift: str

    helmet: bool = True

    gloves: bool = True

    vest: bool = True

    fatigue: int = 0

    permit_id: str | None = None

    active: bool = True