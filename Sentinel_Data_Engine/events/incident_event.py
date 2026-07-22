"""
============================================================
Sentinel Data Engine

Incident Event

Implements the official IncidentEvent contract.
============================================================
"""

from dataclasses import dataclass

from events.contract_event import ContractEvent


@dataclass
class IncidentEvent(ContractEvent):

    def __post_init__(self):

        self.event_type = "incident.reported"

    def set_incident_data(

        self,

        event_type,

        incident_id,

        incident_type,

        severity,

        description,

        root_cause,

        contributing_factors,

        injuries,

        fatalities,

        remediation_taken,

        regulatory_report_required,

        regulatory_reference,

        investigation_findings

    ):

        self.event_type = event_type

        self.payload = {

            "incident_id": incident_id,

            "incident_type": incident_type,

            "severity": severity,

            "description": description,

            "root_cause": root_cause,

            "contributing_factors": contributing_factors,

            "injuries": injuries,

            "fatalities": fatalities,

            "remediation_taken": remediation_taken,

            "regulatory_report_required": regulatory_report_required,

            "regulatory_reference": regulatory_reference,

            "investigation_findings": investigation_findings

        }

        return self