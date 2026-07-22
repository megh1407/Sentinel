"""
============================================================
Sentinel Data Engine

Timeline Generator

Maintains the simulation clock and provides
time-related information for all generators.
============================================================
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TimelineState:

    tick: int

    timestamp: datetime

    day: int

    hour: int

    minute: int

    shift: str

    is_weekend: bool


class TimelineGenerator:

    def __init__(

        self,

        start_time=datetime(2026, 1, 1, 6, 0, 0),

        tick_minutes=5

    ):

        self.start_time = start_time

        self.current_time = start_time

        self.tick_minutes = tick_minutes

        self.tick_count = 0

    # =====================================================

    def get_shift(self):

        hour = self.current_time.hour

        if 6 <= hour < 14:
            return "Morning"

        if 14 <= hour < 22:
            return "Evening"

        return "Night"

    # =====================================================

    def is_weekend(self):

        return self.current_time.weekday() >= 5

    # =====================================================

    def state(self):

        return TimelineState(

            tick=self.tick_count,

            timestamp=self.current_time,

            day=(self.current_time - self.start_time).days + 1,

            hour=self.current_time.hour,

            minute=self.current_time.minute,

            shift=self.get_shift(),

            is_weekend=self.is_weekend()

        )

    # =====================================================

    def advance(self):

        self.current_time += timedelta(

            minutes=self.tick_minutes

        )

        self.tick_count += 1

        return self.state()

    # =====================================================

    def reset(self):

        self.current_time = self.start_time

        self.tick_count = 0


# ==========================================================
# Test
# ==========================================================

if __name__ == "__main__":

    timeline = TimelineGenerator()

    for _ in range(10):

        state = timeline.advance()

        print(

            f"[{state.tick}] "

            f"{state.timestamp} | "

            f"Day {state.day} | "

            f"{state.shift}"

        )