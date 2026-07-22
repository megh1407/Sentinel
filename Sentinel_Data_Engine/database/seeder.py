"""
============================================================
Sentinel Data Engine

Database Seeder

Responsible for inserting contract-compliant
events into PostgreSQL.

Author : Sentinel Data Engine
============================================================
"""

import json

from database.postgres import db


class DatabaseSeeder:

    def __init__(self):

        self.db = db

    # =====================================================
    # Sites
    # =====================================================

    def insert_site(

        self,

        site_code,

        name,

        country,

        timezone

    ):

        query = """

        INSERT INTO sites
        (
            site_code,
            name,
            country,
            timezone
        )

        VALUES
        (%s,%s,%s,%s)

        ON CONFLICT(site_code)

        DO NOTHING;

        """

        self.db.execute(

            query,

            (

                site_code,

                name,

                country,

                timezone

            )

        )

    # =====================================================
    # Zones
    # =====================================================

    def insert_zone(

        self,

        site_id,

        zone_code,

        name,

        zone_type,

        floor=0

    ):

        query = """

        INSERT INTO zones
        (

            site_id,

            zone_code,

            name,

            zone_type,

            floor

        )

        VALUES

        (%s,%s,%s,%s,%s)

        ON CONFLICT(site_id,zone_code)

        DO NOTHING;

        """

        self.db.execute(

            query,

            (

                site_id,

                zone_code,

                name,

                zone_type,

                floor

            )

        )

    # =====================================================
    # Audit Log
    # =====================================================

    def insert_audit_log(

        self,

        event

    ):

        event_dict = event.to_dict()

        query = """

        INSERT INTO audit_logs
        (

            event_id,

            event_type,

            source,

            site_id,

            zone_id,

            correlation_id,

            causation_id,

            schema_version,

            payload

        )

        VALUES

        (

            %s,

            %s,

            %s,

            %s,

            %s,

            %s,

            %s,

            %s,

            %s::jsonb

        );

        """

        self.db.execute(

            query,

            (

                event_dict["event_id"],

                event_dict["event_type"],

                event_dict["source"],

                event_dict["site_id"],

                event_dict["zone_id"],

                event_dict["correlation_id"],

                event_dict["causation_id"],

                event_dict["schema_version"],

                json.dumps(event_dict)

            )

        )

    # =====================================================
    # Risk History
    # =====================================================

    def insert_risk(

        self,

        event,

        score,

        severity,

        contributors,

        explanation

    ):

        query = """

        INSERT INTO risk_history
        (

            event_id,

            site_id,

            zone_id,

            score,

            severity,

            contributors,

            explanation_summary,

            computed_at

        )

        VALUES

        (

            %s,

            %s,

            %s,

            %s,

            %s,

            %s::jsonb,

            %s,

            NOW()

        );

        """

        self.db.execute(

            query,

            (

                event.event_id,

                event.site_id,

                event.zone_id,

                score,

                severity,

                json.dumps(contributors),

                explanation

            )

        )

    # =====================================================
    # Agent Result
    # =====================================================

    def insert_agent_result(

        self,

        event,

        agent_id,

        confidence,

        processing_time,

        payload

    ):

        query = """

        INSERT INTO agent_results
        (

            event_id,

            agent_id,

            agent_version,

            result_type,

            site_id,

            zone_id,

            confidence,

            processing_time_ms,

            payload

        )

        VALUES

        (

            %s,

            %s,

            '1.0',

            %s,

            %s,

            %s,

            %s,

            %s,

            %s::jsonb

        );

        """

        self.db.execute(

            query,

            (

                event.event_id,

                agent_id,

                event.event_type,

                event.site_id,

                event.zone_id,

                confidence,

                processing_time,

                json.dumps(payload)

            )

        )

    # =====================================================
    # Incident
    # =====================================================

    def insert_incident(

        self,

        site_id,

        zone_id,

        event_id,

        incident_type,

        severity,

        description

    ):

        query = """

        INSERT INTO incidents
        (

            site_id,

            zone_id,

            event_id,

            incident_type,

            severity,

            description,

            occurred_at

        )

        VALUES

        (

            %s,

            %s,

            %s,

            %s,

            %s,

            %s,

            NOW()

        );

        """

        self.db.execute(

            query,

            (

                site_id,

                zone_id,

                event_id,

                incident_type,

                severity,

                description

            )

        )

    # =====================================================
    # Close
    # =====================================================

    def close(self):

        self.db.close()


# ==========================================================
# Singleton
# ==========================================================

seeder = DatabaseSeeder()