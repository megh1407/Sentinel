"""
============================================================
Sentinel Data Engine

CSV Exporter

Exports contract-compliant events to CSV.
============================================================
"""

import csv
from pathlib import Path


class CSVExporter:

    def __init__(self, output_dir="datasets/raw"):

        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(

            parents=True,

            exist_ok=True

        )

    # =====================================================

    def export(self, events, filename):

        path = self.output_dir / filename

        rows = []

        for event in events:

            if hasattr(event, "to_dict"):

                rows.append(event.to_dict())

            elif isinstance(event, dict):

                rows.append(event)

        if not rows:

            return

        headers = sorted(

            {

                key

                for row in rows

                for key in row.keys()

            }

        )

        with open(

            path,

            "w",

            newline="",

            encoding="utf-8"

        ) as file:

            writer = csv.DictWriter(

                file,

                fieldnames=headers,

                extrasaction="ignore"

            )

            writer.writeheader()

            writer.writerows(rows)

        return path