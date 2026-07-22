"""
============================================================
Sentinel Data Engine

Schema Validator

Supports JSON Schema Draft-07 with local $ref resolution.
============================================================
"""

import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver


class SchemaValidator:

    def __init__(self):

        self.schema_dir = Path("contracts/events/v1")

        self.schemas = {}

        self.validators = {}

        self.load_all()

    # =====================================================

    def load_all(self):

        if not self.schema_dir.exists():

            print(f"Schema directory not found: {self.schema_dir}")

            return

        # -------------------------------
        # Load every schema first
        # -------------------------------

        for file in self.schema_dir.glob("*.schema.json"):

            try:

                with open(file, "r", encoding="utf-8") as f:

                    schema = json.load(f)

                name = file.name.replace(".schema.json", "")

                self.schemas[name] = schema

            except Exception as e:

                print(f"Failed to load {file.name}: {e}")

        # -------------------------------
        # Create validators
        # -------------------------------

        base_uri = self.schema_dir.resolve().as_uri() + "/"

        resolver = RefResolver(
            base_uri=base_uri,
            referrer={}
        )

        for name, schema in self.schemas.items():

            self.validators[name] = Draft7Validator(
                schema,
                resolver=resolver
            )

    # =====================================================

    def validate_event(

        self,

        schema_name,

        event

    ):

        if hasattr(event, "to_dict"):

            event = event.to_dict()

        validator = self.validators.get(schema_name)

        if validator is None:

            return False, f"Schema '{schema_name}' not loaded."

        errors = sorted(

            validator.iter_errors(event),

            key=lambda e: e.path

        )

        if not errors:

            return True, None

        error = errors[0]

        location = " -> ".join(

            str(x)

            for x in error.absolute_path

        )

        return (

            False,

            f"{location}: {error.message}"

        )

    # =====================================================

    def loaded_schemas(self):

        return sorted(

            self.schemas.keys()

        )

    # =====================================================

    def print_loaded(self):

        print("\nLoaded Schemas\n")

        for schema in sorted(self.schemas):

            print(" -", schema)

        print()