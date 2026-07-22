"""
============================================================
Sentinel Data Engine

Export Manager
============================================================
"""

from exporters.csv_exporter import CSVExporter
from exporters.json_exporter import JSONExporter


class ExportManager:

    def __init__(self):

        self.csv = CSVExporter()

        self.json = JSONExporter()

    # =====================================================

    def export(self, events):

        self.csv.export(

            events,

            "events.csv"

        )

        self.json.export(

            events,

            "events.json"

        )

        print(

            "Export Complete"

        )