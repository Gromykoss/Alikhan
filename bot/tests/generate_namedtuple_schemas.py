#!/usr/bin/env python3
"""Generate draft-07 JSON Schemas for data_sources NamedTuple contracts."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, get_args, get_origin


BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

import data_sources


SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
NAMEDTUPLE_NAMES = [
    "WeatherData",
    "IncidentCount",
    "StaffOrg",
    "StaffData",
    "VolumeData",
    "PhotoFile",
    "PhotoData",
    "AIBHeadcount",
    "EquipmentItem",
    "EquipmentData",
    "MaterialItem",
    "MaterialData",
    "ActivePhases",
    "PlanData",
    "CodeSource",
]


def is_namedtuple_type(annotation: Any) -> bool:
    return (
        isinstance(annotation, type)
        and issubclass(annotation, tuple)
        and hasattr(annotation, "_fields")
        and hasattr(annotation, "__annotations__")
    )


def schema_for_type(annotation: Any) -> dict[str, Any]:
    if isinstance(annotation, str):
        return {}
    if is_namedtuple_type(annotation):
        return {"$ref": f"#/definitions/{annotation.__name__}"}
    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is dict:
        return {"type": "object"}
    if annotation in (list, set, tuple):
        return {"type": "array"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (list, set):
        item_type = args[0] if args else Any
        return {"type": "array", "items": schema_for_type(item_type)}
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": schema_for_type(args[0])}
        if args:
            return {
                "type": "array",
                "items": [schema_for_type(arg) for arg in args],
                "additionalItems": False,
                "minItems": len(args),
                "maxItems": len(args),
            }
        return {"type": "array"}
    if origin is dict:
        value_type = args[1] if len(args) == 2 else Any
        return {"type": "object", "additionalProperties": schema_for_type(value_type)}

    return {}


def namedtuple_schema(cls: type) -> dict[str, Any]:
    annotations = cls.__annotations__
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(cls._fields),
        "properties": {
            field: schema_for_type(annotations[field])
            for field in cls._fields
        },
    }


def generate_schemas() -> dict[str, dict[str, Any]]:
    classes = {name: getattr(data_sources, name) for name in NAMEDTUPLE_NAMES}
    definitions = {
        name: namedtuple_schema(cls)
        for name, cls in classes.items()
    }
    return {
        name: {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": name,
            **definitions[name],
            "definitions": definitions,
        }
        for name in NAMEDTUPLE_NAMES
    }


def write_schemas(schema_dir: Path = SCHEMA_DIR) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    for name, schema in generate_schemas().items():
        path = schema_dir / f"{name}.json"
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    write_schemas()
