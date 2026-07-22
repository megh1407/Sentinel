"""
============================================================
SENTINEL DATA ENGINE

Main Entry Point

Runs the complete synthetic data generation pipeline.

============================================================
"""

from config.logging_config import logger

from generators.master_event_generator import MasterEventGenerator
from exporters.export_manager import ExportManager
from validators.schema_validator import SchemaValidator
from database.seeder import DatabaseSeeder


# ==========================================================
# Configuration
# ==========================================================

TOTAL_TICKS = 100

ENABLE_DATABASE = False
ENABLE_EXPORT = True
ENABLE_VALIDATION = True


# ==========================================================
# Schema Mapping
# ==========================================================

SCHEMA_MAP = {

    "SensorEvent": "sensor_event",

    "WorkerEvent": "worker_events",

    "EnvironmentalEvent": "environmental_event",

    "EquipmentStateEvent": "equipment_state",

    "PermitEvent": "permit_events",

    "IncidentEvent": "incident_event",

    "RiskEvent": "risk_score",

    "AgentResultEvent": "agent_result",

    "ActionRequestEvent": "action_request",

    "ActionResultEvent": "action_result"

}


# ==========================================================
# Main
# ==========================================================

def main():

    logger.info("=" * 60)
    logger.info("Starting SENTINEL Data Engine")
    logger.info("=" * 60)

    generator = MasterEventGenerator()

    exporter = ExportManager()

    validator = SchemaValidator()

    seeder = DatabaseSeeder()

    exported_events = []

    total_events = 0

    validation_failures = 0

    # =====================================================
    # Simulation Loop
    # =====================================================

    for tick in range(TOTAL_TICKS):

        simulation = generator.tick()

        events = simulation["events"]

        logger.info(

            f"Tick {tick + 1:03d} | "

            f"{len(events)} Events"

        )

        for event in events:

            # =================================================
            # Validation
            # =================================================

            if ENABLE_VALIDATION:

                schema_name = SCHEMA_MAP.get(

                    event.__class__.__name__

                )

                if schema_name:

                    valid, error = validator.validate_event(

                        schema_name,

                        event

                    )

                    if not valid:

                        validation_failures += 1

                        logger.warning(

                            f"[VALIDATION] {schema_name}"

                        )

                        logger.warning(error)

            # =================================================
            # Database
            # =================================================

            if ENABLE_DATABASE:

                try:

                    seeder.insert_audit_log(event)

                except Exception as e:

                    logger.error(e)

            exported_events.append(event)

            total_events += 1

    # =====================================================
    # Export
    # =====================================================

    if ENABLE_EXPORT:

        logger.info("Exporting datasets...")

        exporter.export(exported_events)

        logger.info("Export completed.")

    # =====================================================
    # Close Database
    # =====================================================

    try:

        seeder.close()

    except Exception:

        pass

    # =====================================================
    # Summary
    # =====================================================

    logger.info("=" * 60)

    logger.info("Simulation Finished Successfully")

    logger.info(f"Ticks Executed        : {TOTAL_TICKS}")

    logger.info(f"Events Generated      : {total_events}")

    logger.info(f"Validation Failures   : {validation_failures}")

    logger.info("=" * 60)


# ==========================================================

if __name__ == "__main__":

    main()