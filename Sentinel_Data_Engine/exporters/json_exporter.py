"""
============================================================
Sentinel Data Engine

JSON Exporter
============================================================
"""

import json
from pathlib import Path


class JSONExporter:

    def __init__(self, output_dir="datasets/raw"):

        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(

            parents=True,

            exist_ok=True

        )

    # =====================================================

    def export(self, events, filename):

        path = self.output_dir / filename

        data = []

        for event in events:

            if hasattr(event, "to_dict"):

                data.append(

                    event.to_dict()

                )

            else:

                data.append(event)

        with open(

            path,

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                data,

                file,

                indent=4,

                default=str

            )

        return path