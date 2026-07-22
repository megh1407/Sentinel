"""
============================================================
Sentinel Data Engine

Scenario Generator 2.0

Finite State Machine (FSM)

Generates realistic industrial scenario sequences
instead of random independent events.
============================================================
"""

import random
from dataclasses import dataclass


@dataclass
class Scenario:

    name: str

    severity: str

    duration: int

    next_states: list


class ScenarioGenerator:

    def __init__(self):

        self.scenarios = {

            "NORMAL_OPERATION": Scenario(

                "NORMAL_OPERATION",

                "low",

                60,

                [

                    ("HOT_WORK", 0.20),

                    ("MAINTENANCE", 0.15),

                    ("GAS_LEAK", 0.05),

                    ("NORMAL_OPERATION", 0.60)

                ]

            ),

            "HOT_WORK": Scenario(

                "HOT_WORK",

                "moderate",

                20,

                [

                    ("NORMAL_OPERATION", 0.70),

                    ("FIRE", 0.20),

                    ("GAS_LEAK", 0.10)

                ]

            ),

            "MAINTENANCE": Scenario(

                "MAINTENANCE",

                "low",

                30,

                [

                    ("NORMAL_OPERATION", 0.75),

                    ("EQUIPMENT_FAILURE", 0.25)

                ]

            ),

            "GAS_LEAK": Scenario(

                "GAS_LEAK",

                "high",

                15,

                [

                    ("NORMAL_OPERATION", 0.45),

                    ("FIRE", 0.25),

                    ("EXPLOSION", 0.10),

                    ("GAS_LEAK", 0.20)

                ]

            ),

            "FIRE": Scenario(

                "FIRE",

                "critical",

                10,

                [

                    ("NORMAL_OPERATION", 0.50),

                    ("EXPLOSION", 0.20),

                    ("FIRE", 0.30)

                ]

            ),

            "EQUIPMENT_FAILURE": Scenario(

                "EQUIPMENT_FAILURE",

                "high",

                15,

                [

                    ("MAINTENANCE", 0.50),

                    ("NORMAL_OPERATION", 0.50)

                ]

            ),

            "EXPLOSION": Scenario(

                "EXPLOSION",

                "catastrophic",

                5,

                [

                    ("NORMAL_OPERATION", 1.00)

                ]

            )

        }

        self.current = self.scenarios["NORMAL_OPERATION"]

        self.remaining_ticks = self.current.duration

    # =====================================================

    def _transition(self):

        transitions = self.current.next_states

        states = [state for state, _ in transitions]

        weights = [weight for _, weight in transitions]

        next_state = random.choices(

            states,

            weights=weights,

            k=1

        )[0]

        self.current = self.scenarios[next_state]

        self.remaining_ticks = self.current.duration

    # =====================================================

    def tick(self):

        self.remaining_ticks -= 1

        if self.remaining_ticks <= 0:

            self._transition()

        return self.current

    # =====================================================

    def current_state(self):

        return {

            "name": self.current.name,

            "severity": self.current.severity,

            "remaining_ticks": self.remaining_ticks

        }


if __name__ == "__main__":

    generator = ScenarioGenerator()

    for _ in range(100):

        scenario = generator.tick()

        print(

            scenario.name,

            scenario.severity,

            generator.remaining_ticks

        )