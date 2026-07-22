"""
Risk Model
"""

from dataclasses import dataclass


@dataclass
class Risk:

    score: float

    severity: str

    explanation: str