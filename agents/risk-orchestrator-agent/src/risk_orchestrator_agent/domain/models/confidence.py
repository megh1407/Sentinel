"""ConfidenceScore and Age value objects (Phase 2.2 §4.2, Phase 2.5 §5).

Pure frozen dataclasses. Zero I/O. Domain layer may depend on nothing
outside the standard library and sibling `domain/models/*` modules
(Phase 3.1 §3.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    """A [0,1] certainty measure attached to any claim (Phase 2.5 §5).

    Never presented separately from the claim it qualifies (Phase 2.3 §10.5,
    Phase 2.2 §12.3's "absence is never presence of safety" rule extends
    here: a low value is reported, never suppressed).
    """

    value: float
    derivation_method: str = "carried_through"

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            object.__setattr__(self, "value", min(1.0, max(0.0, self.value)))


@dataclass(frozen=True, slots=True)
class Age:
    """Wall-clock time since a fact's `analyzed_at` (Phase 2.2 §4.2).

    Every downstream staleness/expiration decision (Phase 2.2 §2, §14) is
    computed from this field.
    """

    duration: timedelta

    @property
    def seconds(self) -> float:
        return self.duration.total_seconds()

    def exceeds(self, threshold: timedelta) -> bool:
        return self.duration > threshold
