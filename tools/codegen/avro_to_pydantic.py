"""Deterministic Avro -> Pydantic code generator.

Per Artifact 4 §5: "Codegen runs Avro -> everything else, one direction
only. Populates libs/sentinel_contracts/generated/... Generated output is
never hand-edited; CI fails if regenerating from source wouldn't produce
identical committed output."

Per Artifact 4 §10, this tool lives at tools/codegen/. Per Artifact 12
Phase 3 Step 11, its output populates libs/sentinel_contracts/generated/
for the first time.

This walks the canonical Avro tree (contracts/common/, contracts/events/,
contracts/agent-contracts/) and emits one Python module per top-level
record, mirroring the naming/structure conventions already established by
the hand-written sentinel_contracts/ package (flat-inlined envelope
fields -- Avro has no inheritance, so nothing here is generated as a
Python base/subclass relationship across files; nested Avro records/enums
become nested Pydantic/Enum classes in the same module; a versioned
`{Name}V{n}` alias class carries SCHEMA_VERSION/SCHEMA_SUBJECT; a
SCHEMA_TIMESTAMP_FIELDS ClassVar names any timestamp-millis fields).

Usage: python3 tools/codegen/avro_to_pydantic.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_ROOT = REPO_ROOT / "contracts"
COMMON_DIR = CONTRACTS_ROOT / "common"
EVENTS_DIR = CONTRACTS_ROOT / "events"
AGENT_CONTRACTS_DIR = CONTRACTS_ROOT / "agent-contracts"
OUT_ROOT = REPO_ROOT / "libs" / "sentinel_contracts" / "generated"

# Mirrors schema_loader.py's COMMON_SCHEMA_ORDER exactly (single source of
# truth for common-type load/dependency order; duplicated here rather than
# imported since schema_loader.py is a root script, not a package -- kept
# in lockstep manually, same as schema_loader.py itself is hand-maintained).
COMMON_SCHEMA_ORDER: list[str] = [
    "enums/Environment.avsc",
    "Metadata.avsc",
    "GeoLocation.avsc",
    "EvidenceItem.avsc",
    "RiskContributor.avsc",
    "enums/ConfidenceDerivation.avsc",
    "ConfidenceScore.avsc",
    "ExplanationObject.avsc",
    "BaseEvent.avsc",
]

HEADER = '"""Generated from {source}. DO NOT HAND-EDIT -- regenerate via tools/codegen/avro_to_pydantic.py"""\n'


def to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class ModuleBuilder:
    """Accumulates the class definitions and imports needed for one
    generated .py file, in dependency order (innermost/earliest-referenced
    types first, so a class is always defined before it's used)."""

    def __init__(self, common_classes: dict[str, str]):
        self.common_classes = common_classes  # class name -> module name, e.g. "Metadata" -> "metadata"
        self.body_blocks: list[str] = []
        self.defined_names: set[str] = set()
        self.needs_uuid = False
        self.needs_datetime = False
        self.needs_enum = False
        self.needs_field = False
        self.needs_classvar = False
        self.common_imports: set[str] = set()

    def avro_type_to_py(self, t, field_name: str, timestamp_fields: list[str]) -> str:
        """Returns the Python type annotation string for an Avro type,
        emitting any nested class definitions as a side effect."""
        if isinstance(t, str):
            prim = {
                "string": "str", "boolean": "bool", "int": "int",
                "long": "int", "double": "float", "float": "float",
                "bytes": "bytes", "null": "None",
            }
            if t in prim:
                return prim[t]
            # Fully-qualified or bare reference to a named type.
            short = t.rsplit(".", 1)[-1]
            if short in self.common_classes:
                self.common_imports.add(short)
                return short
            return short  # same-file forward/prior reference

        if isinstance(t, list):
            non_null = [x for x in t if x != "null"]
            is_optional = "null" in t
            if len(non_null) == 1:
                inner = self.avro_type_to_py(non_null[0], field_name, timestamp_fields)
            else:
                inner = " | ".join(self.avro_type_to_py(x, field_name, timestamp_fields) for x in non_null)
            return f"{inner} | None" if is_optional else inner

        if isinstance(t, dict):
            logical = t.get("logicalType")
            if t.get("type") == "string" and logical == "uuid":
                self.needs_uuid = True
                return "UUID"
            if t.get("type") == "long" and logical == "timestamp-millis":
                self.needs_datetime = True
                timestamp_fields.append(field_name)
                return "datetime"
            if t["type"] == "array":
                inner = self.avro_type_to_py(t["items"], field_name, timestamp_fields)
                return f"list[{inner}]"
            if t["type"] == "map":
                inner = self.avro_type_to_py(t["values"], field_name, timestamp_fields)
                return f"dict[str, {inner}]"
            if t["type"] == "enum":
                self._emit_enum(t)
                return t["name"]
            if t["type"] == "record":
                self._emit_record(t)
                return t["name"]
            if t["type"] in ("string", "boolean", "int", "long", "double", "float", "bytes"):
                return self.avro_type_to_py(t["type"], field_name, timestamp_fields)
        raise ValueError(f"Unhandled Avro type for field {field_name!r}: {t!r}")

    def _emit_enum(self, t: dict) -> None:
        name = t["name"]
        if name in self.defined_names:
            return
        self.defined_names.add(name)
        self.needs_enum = True
        lines = [f"class {name}(str, Enum):"]
        for sym in t["symbols"]:
            lines.append(f'    {sym} = "{sym}"')
        self.body_blocks.append("\n".join(lines))

    def _emit_record(self, t: dict) -> None:
        name = t["name"]
        if name in self.defined_names:
            return
        self.defined_names.add(name)
        field_lines = []
        timestamp_fields: list[str] = []
        for f in t["fields"]:
            field_lines.append(self._render_field(f, timestamp_fields))
        lines = [f"class {name}(BaseModel):"]
        if t.get("doc"):
            lines.append(f'    """{t["doc"]}"""')
        if timestamp_fields:
            self.needs_classvar = True
            lines.append(f"    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = {timestamp_fields!r}")
        lines.extend(f"    {fl}" for fl in field_lines)
        self.body_blocks.append("\n".join(lines))

    def _render_field(self, f: dict, timestamp_fields: list[str]) -> str:
        py_type = self.avro_type_to_py(f["type"], f["name"], timestamp_fields)
        has_default = "default" in f
        default_val = f.get("default")
        is_optional_type = py_type.endswith("| None")
        if py_type.startswith("list["):
            if has_default and default_val == []:
                self.needs_field = True
                return f"{f['name']}: {py_type} = Field(default_factory=list)"
            return f"{f['name']}: {py_type}"
        if py_type.startswith("dict["):
            if has_default and default_val == {}:
                self.needs_field = True
                return f"{f['name']}: {py_type} = Field(default_factory=dict)"
            return f"{f['name']}: {py_type}"
        if has_default:
            if default_val is None:
                return f"{f['name']}: {py_type} = None"
            if isinstance(default_val, str):
                return f'{f["name"]}: {py_type} = "{default_val}"'
            return f"{f['name']}: {py_type} = {default_val!r}"
        if is_optional_type:
            return f"{f['name']}: {py_type} = None"
        return f"{f['name']}: {py_type}"

    def render_top_level(self, schema: dict) -> tuple[str, list[str]]:
        """Emits the top-level record's class and returns (class_name, timestamp_fields)."""
        name = schema["name"]
        timestamp_fields: list[str] = []
        field_lines = [self._render_field(f, timestamp_fields) for f in schema["fields"]]
        self.defined_names.add(name)
        lines = [f"class {name}(BaseModel):"]
        if schema.get("doc"):
            lines.append(f'    """{schema["doc"]}"""')
        if timestamp_fields:
            self.needs_classvar = True
            lines.append(f"    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = {timestamp_fields!r}")
        lines.extend(f"    {fl}" for fl in field_lines)
        self.body_blocks.append("\n".join(lines))
        return name, timestamp_fields

    def render_module(self, source_rel: str, top_class: str, version: int, subject: str) -> str:
        self.needs_classvar = True
        imports = [HEADER.format(source=source_rel), "from __future__ import annotations"]
        if self.needs_datetime:
            imports.append("from datetime import datetime")
        if self.needs_enum:
            imports.append("from enum import Enum")
        field_import = "BaseModel, Field" if self.needs_field else "BaseModel"
        imports.append(f"from pydantic import {field_import}")
        for cname in sorted(self.common_imports):
            mod = self.common_classes[cname]
            imports.append(f"from ..common.{mod} import {cname}")
        imports.append("from typing import ClassVar")
        if self.needs_uuid:
            imports.append("from uuid import UUID")
        header = "\n".join(imports)
        body = "\n\n\n".join(self.body_blocks)
        alias = (
            f"class {top_class}V{version}({top_class}):\n"
            f'    """Versioned, registry-addressable alias of {top_class} '
            f"(schema subject '{subject}', version {version}).\"\"\"\n"
            f"    SCHEMA_VERSION: ClassVar[int] = {version}\n"
            f"    SCHEMA_SUBJECT: ClassVar[str] = '{subject}'"
        )
        return f"{header}\n\n\n{body}\n\n\n{alias}\n"


def load_raw(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def build_common_classes() -> dict[str, str]:
    """Maps every common class name to its generated module name (without
    building the modules themselves yet -- needed so downstream event/
    agent-contract modules know which names are common-package imports)."""
    mapping = {}
    for rel in COMMON_SCHEMA_ORDER:
        raw = load_raw(COMMON_DIR / rel)
        mod = to_snake(raw["name"])
        mapping[raw["name"]] = mod
    return mapping


def generate_common(common_classes: dict[str, str]) -> None:
    out_dir = OUT_ROOT / "common"
    out_dir.mkdir(parents=True, exist_ok=True)
    module_names = []
    for rel in COMMON_SCHEMA_ORDER:
        raw = load_raw(COMMON_DIR / rel)
        mb = ModuleBuilder(common_classes)
        if raw["type"] == "enum":
            mb._emit_enum(raw)
            top_name = raw["name"]
            needs_enum, needs_uuid, needs_datetime, needs_field = True, False, False, False
        else:
            top_name, _ = mb.render_top_level(raw)
            needs_enum, needs_uuid, needs_datetime, needs_field = (
                mb.needs_enum, mb.needs_uuid, mb.needs_datetime, mb.needs_field
            )
        mod = to_snake(top_name)
        module_names.append((top_name, mod))

        imports = [HEADER.format(source=f"contracts/common/{rel}"), "from __future__ import annotations"]
        if needs_datetime:
            imports.append("from datetime import datetime")
        if needs_enum:
            imports.append("from enum import Enum")
        if raw["type"] != "enum":
            field_import = "BaseModel, Field" if needs_field else "BaseModel"
            imports.append(f"from pydantic import {field_import}")
        for cname in sorted(mb.common_imports):
            if cname == top_name:
                continue
            cmod = common_classes[cname]
            imports.append(f"from .{cmod} import {cname}")
        if raw["type"] != "enum":
            imports.append("from typing import ClassVar")
        if mb.needs_uuid:
            imports.append("from uuid import UUID")
        header = "\n".join(imports)
        body = "\n\n\n".join(mb.body_blocks)
        (out_dir / f"{mod}.py").write_text(f"{header}\n\n\n{body}\n")

    init_lines = [f"from .{mod} import {name}" for name, mod in module_names]
    (out_dir / "__init__.py").write_text("\n".join(init_lines) + "\n")


def generate_group(base_dir: Path, out_subdir: str, common_classes: dict[str, str],
                    discover) -> None:
    out_dir = OUT_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    init_lines = []
    for source_rel, version, path in discover():
        raw = load_raw(path)
        mb = ModuleBuilder(common_classes)
        top_class, _ = mb.render_top_level(raw)
        subject = f"{top_class}-value"
        module_src = mb.render_module(source_rel, top_class, version, subject)
        mod_name = f"{to_snake(top_class)}_v{version}"
        (out_dir / f"{mod_name}.py").write_text(module_src)
        alias = f"{top_class}V{version}"
        init_lines.append(f"from .{mod_name} import {alias}")
    (out_dir / "__init__.py").write_text("\n".join(init_lines) + "\n")


def discover_events():
    for event_dir in sorted(EVENTS_DIR.iterdir()):
        if not event_dir.is_dir():
            continue
        for version_dir in sorted(event_dir.glob("v*")):
            path = version_dir / "schema.avsc"
            if not path.exists():
                continue
            version = int(version_dir.name.lstrip("v"))
            yield f"contracts/events/{event_dir.name}/{version_dir.name}/schema.avsc", version, path


def discover_agent_contracts():
    for version_dir in sorted(AGENT_CONTRACTS_DIR.iterdir()):
        if not version_dir.is_dir():
            continue
        version = int(version_dir.name.lstrip("v"))
        for path in sorted(version_dir.glob("*.avsc")):
            yield f"contracts/agent-contracts/{version_dir.name}/{path.name}", version, path


def main() -> None:
    if OUT_ROOT.exists():
        import shutil
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    (OUT_ROOT / "__init__.py").write_text(
        '"""Generated typed models. DO NOT HAND-EDIT -- regenerate via tools/codegen/avro_to_pydantic.py"""\n'
    )
    common_classes = build_common_classes()
    generate_common(common_classes)
    generate_group(EVENTS_DIR, "events", common_classes, discover_events)
    generate_group(AGENT_CONTRACTS_DIR, "agent_contracts", common_classes, discover_agent_contracts)
    print("Generation complete.")


if __name__ == "__main__":
    sys.exit(main())
