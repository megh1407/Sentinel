"""
============================================================
Sentinel Data Engine

Permit Generator

Creates contract-compliant PermitEvent objects.
============================================================
"""

import random
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from config.constants import ZONES

from events.permit_event import PermitEvent


class PermitGenerator:

    PERMIT_TYPES = [

        "hot_work",

        "confined_space",

        "electrical",

        "chemical",

        "height",

        "radiation",

        "excavation",

        "cold_work",

        "line_break"

    ]

    STATUS = [

        ("permit.created", "draft"),

        ("permit.approved", "pending_approval"),

        ("permit.activated", "active"),

        ("permit.suspended", "suspended"),

        ("permit.revoked", "revoked"),

        ("permit.expired", "expired")

    ]

    CONDITIONS = [

        "Area Barricaded",

        "Gas Test Completed",

        "Fire Watch Assigned",

        "LOTO Verified",

        "PPE Verified"

    ]

    def __init__(self):

        pass

    # =====================================================

    def generate(

        self,

        site_id,

        zone_id,

        worker_id

    ):

        permit_id = str(uuid4())

        now = datetime.now(timezone.utc)

        valid_until = now + timedelta(hours=8)

        event_type, lifecycle = random.choice(

            self.STATUS

        )

        event = PermitEvent(

            site_id=site_id,

            zone_id=zone_id

        )

        event.set_permit_data(

            event_type=event_type,

            permit_id=permit_id,

            permit_type=random.choice(

                self.PERMIT_TYPES

            ),

            lifecycle_status=lifecycle,

            issued_to=worker_id,

            issued_by="Safety Officer",

            valid_from=now.isoformat(),

            valid_until=valid_until.isoformat(),

            zone_restrictions=[

                zone_id

            ],

            concurrent_permits=[],

            conditions=random.sample(

                self.CONDITIONS,

                random.randint(2,4)

            ),

            gas_test_required=random.choice(

                [True, False]

            ),

            isolation_points=[

                "ISO-101",

                "ISO-205"

            ]

        )

        return event