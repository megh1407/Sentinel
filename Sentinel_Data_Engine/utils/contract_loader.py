"""
Sentinel Data Engine
Contract Loader

Loads every JSON Schema and Avro Schema
from the Sentinel contracts directory.
"""

from pathlib import Path
import json


class ContractLoader:

    def __init__(self, contract_root="contracts"):

        self.contract_root = Path(contract_root)

        self.schemas = {}

    # =========================================================

    def load_json_schema(self, file_path):

        with open(file_path, "r", encoding="utf-8") as f:

            return json.load(f)

    # =========================================================

    def discover(self):

        """
        Discover every JSON schema inside contracts.
        """

        for file in self.contract_root.rglob("*.json"):

            try:

                self.schemas[file.stem] = self.load_json_schema(file)

            except Exception as e:

                print(f"Failed to load {file}")

                print(e)

    # =========================================================

    def get(self, name):

        return self.schemas.get(name)

    # =========================================================

    def list_contracts(self):

        return list(self.schemas.keys())


# =============================================================
# Test
# =============================================================

if __name__ == "__main__":

    loader = ContractLoader()

    loader.discover()

    print()

    print("=" * 60)

    print("Loaded Contracts")

    print("=" * 60)

    for contract in loader.list_contracts():

        print(contract)

    print("=" * 60)