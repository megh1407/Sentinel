"""
============================================================
Sentinel Data Engine

Action Generator

Creates ActionRequest and ActionResult events
from RiskScore events.
============================================================
"""

import random
from uuid import uuid4
from datetime import datetime, timezone

from events.action_request_event import ActionRequestEvent
from events.action_result_event import ActionResultEvent


class ActionGenerator:

    ACTION_MATRIX = {

        "LOW": (
            "ALERT_OPERATOR",
            "LOW"
        ),

        "MEDIUM": (
            "NOTIFY_MAINTENANCE",
            "MEDIUM"
        ),

        "HIGH": (
            "SUSPEND_PERMIT",
            "HIGH"
        ),

        "CRITICAL": (
            "EVACUATE_ZONE",
            "IMMEDIATE"
        ),

        "LOCKDOWN": (
            "LOCKOUT_REQUEST",
            "IMMEDIATE"
        )

    }

    # =====================================================

    def generate(

        self,

        site_id,

        zone_id,

        risk_event

    ):

        risk = risk_event.payload

        risk_level = risk["risk_level"]

        risk_id = risk["risk_id"]

        action_type, urgency = self.ACTION_MATRIX.get(

            risk_level,

            (

                "ALERT_OPERATOR",

                "LOW"

            )

        )

        action_id = str(

            uuid4()

        )

        # =================================================
        # Action Request
        # =================================================

        request = ActionRequestEvent()

        request.site_id = site_id

        request.zone_id = zone_id

        request.metadata = {

            "simulation": True,

            "source": "ResponseAgent"

        }

        request.set_action_request(

            action_id=action_id,

            risk_id=risk_id,

            action_type=action_type,

            target_ref=zone_id,

            requested_by="response-agent",

            urgency=urgency,

            requires_human_approval=(

                urgency != "LOW"

            ),

            requires_dual_control=(

                risk_level in [

                    "CRITICAL",

                    "LOCKDOWN"

                ]

            ),

            confidence=0.97,

            summary=f"{action_type} recommended due to {risk_level} risk."

        )

        # =================================================
        # Simulated Decision
        # =================================================

        if risk_level == "LOW":

            outcome = "APPROVED"

        elif risk_level == "MEDIUM":

            outcome = random.choice(

                [

                    "APPROVED",

                    "EXECUTED"

                ]

            )

        elif risk_level == "HIGH":

            outcome = "EXECUTED"

        elif risk_level == "CRITICAL":

            outcome = "EXECUTED"

        else:

            outcome = "EXECUTED"

        executed_at = None

        approved_by = None

        failure_reason = None

        downstream = None

        if outcome == "EXECUTED":

            executed_at = int(

                datetime.now(

                    timezone.utc

                ).timestamp() * 1000

            )

            approved_by = "policy-gateway-auto"

            downstream = "ACTION_COMPLETED"

        elif outcome == "FAILED":

            failure_reason = "Execution failure"

        # =================================================
        # Action Result
        # =================================================

        result = ActionResultEvent()

        result.site_id = site_id

        result.zone_id = zone_id

        result.metadata = {

            "simulation": True,

            "source": "ActionPolicyGateway"

        }

        result.correlation_id = request.correlation_id

        result.causation_id = request.event_id

        result.set_action_result(

            action_id=action_id,

            outcome=outcome,

            approved_by=approved_by,

            executed_at=executed_at,

            failure_reason=failure_reason,

            downstream_confirmation=downstream

        )

        return request, result