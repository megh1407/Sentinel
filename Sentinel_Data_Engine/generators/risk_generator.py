"""
============================================================
Sentinel Data Engine

Risk Generator 2.0

Computes explainable risk scores from
actual plant conditions.
============================================================
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from events.risk_event import RiskEvent


class RiskGenerator:

    # =====================================================

    def calculate(self, plant_state):

        score = 0.0
        reasons = []

        # ---------------------------------------------
        # Gas
        # ---------------------------------------------

        if plant_state.gas_ppm > 50:
            gas_score = min(35, plant_state.gas_ppm / 20)
            score += gas_score
            reasons.append(
                f"Gas concentration {plant_state.gas_ppm:.1f} ppm"
            )

        # ---------------------------------------------
        # Temperature
        # ---------------------------------------------

        if plant_state.temperature > 45:
            temp_score = min(20, (plant_state.temperature - 45) * 0.8)
            score += temp_score
            reasons.append(
                f"High temperature {plant_state.temperature:.1f}°C"
            )

        # ---------------------------------------------
        # Machine Temperature
        # ---------------------------------------------

        if plant_state.machine_temperature > 80:
            machine_score = min(
                20,
                (plant_state.machine_temperature - 80) * 0.5
            )

            score += machine_score

            reasons.append(
                "Machine overheating"
            )

        # ---------------------------------------------
        # Vibration
        # ---------------------------------------------

        if plant_state.vibration > 2:

            vib_score = min(
                15,
                plant_state.vibration * 4
            )

            score += vib_score

            reasons.append(
                "Abnormal vibration"
            )

        # ---------------------------------------------
        # Smoke
        # ---------------------------------------------

        if plant_state.smoke:

            score += 20

            reasons.append(
                "Smoke detected"
            )

        # ---------------------------------------------
        # Flame
        # ---------------------------------------------

        if plant_state.flame:

            score += 30

            reasons.append(
                "Open flame detected"
            )

        score = min(score, 100)

        return score, reasons

    # =====================================================

    def level(self, score):

        if score < 20:
            return "LOW"

        elif score < 40:
            return "MEDIUM"

        elif score < 70:
            return "HIGH"

        elif score < 90:
            return "CRITICAL"

        return "LOCKDOWN"

    # =====================================================

    def generate(

        self,

        site_id,

        zone_id,

        plant_state,

        agent_result_ids=None

    ):

        if agent_result_ids is None:

            agent_result_ids = []

        score, reasons = self.calculate(

            plant_state

        )

        risk = RiskEvent()

        risk.site_id = site_id

        risk.zone_id = zone_id

        risk.partition_key = zone_id

        risk.metadata = {

            "generator": "RiskGenerator",

            "simulation": True

        }

        risk.explanation = {

            "summary": "Risk computed from live plant conditions.",

            "confidence": 0.98,

            "factors": reasons

        }

        risk.payload = {

            "risk_id": str(uuid4()),

            "score": round(score, 2),

            "risk_level": self.level(score),

            "contributing_agent_result_ids": agent_result_ids,

            "compound_rules_fired": [],

            "valid_until": int(

                (

                    datetime.now(

                        timezone.utc

                    ) +

                    timedelta(seconds=30)

                ).timestamp() * 1000

            )

        }

        return risk