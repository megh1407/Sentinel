"""
============================================================
Sentinel Data Engine

Master Event Generator

Coordinates the complete simulation pipeline.
============================================================
"""

from generators.timeline_generator import TimelineGenerator
from generators.scenario_generator import ScenarioGenerator
from generators.plant_generator import PlantGenerator
from generators.sensor_generator import SensorGenerator
from generators.environment_generator import EnvironmentGenerator
from generators.worker_generator import WorkerGenerator
from generators.machine_generator import MachineGenerator
from generators.permit_generator import PermitGenerator
from generators.incident_generator import IncidentGenerator
from generators.agent_result_generator import AgentResultGenerator
from generators.risk_generator import RiskGenerator
from generators.action_generator import ActionGenerator


class MasterEventGenerator:

    def __init__(self, site_id="SITE001"):

        self.site_id = site_id

        # =================================================
        # Core Simulation
        # =================================================

        self.timeline = TimelineGenerator()
        self.scenario = ScenarioGenerator()
        self.plant = PlantGenerator()

        # =================================================
        # Event Generators
        # =================================================

        self.sensor = SensorGenerator()
        self.environment = EnvironmentGenerator()
        self.worker = WorkerGenerator()
        self.machine = MachineGenerator()
        self.permit = PermitGenerator()
        self.incident = IncidentGenerator()
        self.agent_result = AgentResultGenerator()
        self.risk = RiskGenerator()
        self.action = ActionGenerator()

    # =====================================================

    def tick(self):

        all_events = []

        # -------------------------------------------------
        # Timeline
        # -------------------------------------------------

        timeline_state = self.timeline.advance()

        # -------------------------------------------------
        # Scenario
        # -------------------------------------------------

        current_scenario = self.scenario.tick()

        # -------------------------------------------------
        # Update Plant
        # -------------------------------------------------

        self.plant.update(current_scenario)

        # -------------------------------------------------
        # Update Workers
        # -------------------------------------------------

        self.worker.update(timeline_state)

        # -------------------------------------------------
        # Update Machines
        # -------------------------------------------------

        self.machine.update()

        # -------------------------------------------------
        # Process Every Zone
        # -------------------------------------------------

        for zone in self.plant.all_zones():

            # =============================================
            # Sensor Events
            # =============================================

            sensor_events = self.sensor.generate(
                self.site_id,
                zone
            )

            all_events.extend(sensor_events)

            # =============================================
            # Environmental Event
            # =============================================

            env_event = self.environment.generate(
                self.site_id,
                zone
            )

            if env_event:
                all_events.append(env_event)

            # =============================================
            # Equipment Events
            # =============================================

            machine_events = self.machine.generate_events(
                self.site_id,
                zone.zone_id
            )

            all_events.extend(machine_events)

            # =============================================
            # Incident Event
            # =============================================

            incident = self.incident.generate(
                self.site_id,
                zone.zone_id,
                current_scenario
            )

            if incident:
                all_events.append(incident)

            # =============================================
            # Agent Result
            # =============================================

            agent_result = self.agent_result.generate(
                site_id=self.site_id,
                zone_id=zone.zone_id,
                subject_ref=zone.zone_id
            )

            if agent_result:
                all_events.append(agent_result)

            # =============================================
            # Risk Event
            # =============================================

            risk = self.risk.generate(
                site_id=self.site_id,
                zone_id=zone.zone_id,
                plant_state=zone,
                agent_result_ids=[
                    agent_result.payload["agent_result_id"]
                ] if agent_result else []
            )

            if risk:
                all_events.append(risk)

            # =============================================
            # Action Request + Action Result
            # =============================================

            if risk:

                action_request, action_result = self.action.generate(
                    site_id=self.site_id,
                    zone_id=zone.zone_id,
                    risk_event=risk
                )

                if action_request:
                    all_events.append(action_request)

                if action_result:
                    all_events.append(action_result)

        # -------------------------------------------------
        # Worker Events
        # -------------------------------------------------

        worker_events = self.worker.generate_events(
            self.site_id
        )

        all_events.extend(worker_events)

        # -------------------------------------------------
        # Permit Events
        # -------------------------------------------------

        workers = self.worker.get_workers()

        for worker in workers:

            permit = self.permit.generate(
                site_id=self.site_id,
                zone_id=worker["zone"],
                worker_id=worker["worker_id"]
            )

            if permit:
                all_events.append(permit)

        # -------------------------------------------------
        # Return Tick
        # -------------------------------------------------

        return {
            "timeline": timeline_state,
            "scenario": current_scenario,
            "events": all_events
        }

    # =====================================================

    def run(self, ticks=100):

        dataset = []

        for _ in range(ticks):

            dataset.append(
                self.tick()
            )

        return dataset


# ==========================================================
# Test
# ==========================================================

if __name__ == "__main__":

    generator = MasterEventGenerator()

    simulation = generator.run(5)

    print("=" * 60)
    print("Simulation Complete")
    print("=" * 60)

    print(f"Ticks : {len(simulation)}")
    print(f"Events in First Tick : {len(simulation[0]['events'])}")

    total_events = sum(
        len(tick["events"])
        for tick in simulation
    )

    print(f"Total Events Generated : {total_events}")