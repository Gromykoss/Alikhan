"""Smoke tests for generated data_sources NamedTuple JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args, get_origin

import jsonschema

import data_sources
from generate_namedtuple_schemas import NAMEDTUPLE_NAMES, generate_schemas


SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def _is_namedtuple_type(annotation: Any) -> bool:
    return (
        isinstance(annotation, type)
        and issubclass(annotation, tuple)
        and hasattr(annotation, "_fields")
        and hasattr(annotation, "__annotations__")
    )


def _sample_for_type(annotation: Any) -> Any:
    if _is_namedtuple_type(annotation):
        return _as_json(_sample_namedtuple(annotation))
    if annotation is str:
        return "sample"
    if annotation is bool:
        return True
    if annotation is int:
        return 1
    if annotation is float:
        return 1.5
    if annotation is dict:
        return {"sample": "value"}
    if annotation in (list, set, tuple):
        return ["sample"]

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is dict:
        value_type = args[1] if len(args) == 2 else str
        return {"sample": _sample_for_type(value_type)}
    if origin in (list, set):
        item_type = args[0] if args else str
        return [_sample_for_type(item_type)]
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return [_sample_for_type(args[0])]
        return [_sample_for_type(arg) for arg in args]

    return None


def _sample_namedtuple(cls: type) -> tuple:
    kwargs = {
        field: _sample_for_type(cls.__annotations__[field])
        for field in cls._fields
    }
    return cls(**kwargs)


def _as_json(value: Any) -> Any:
    if hasattr(value, "_asdict"):
        return {key: _as_json(item) for key, item in value._asdict().items()}
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_as_json(item) for item in value]
    return value


def test_namedtuple_schema_files_exist_parse_and_match_generator():
    generated = generate_schemas()
    assert set(generated) == set(NAMEDTUPLE_NAMES)

    for name, expected_schema in generated.items():
        path = SCHEMA_DIR / f"{name}.json"
        assert path.exists(), f"schema отсутствует: {path}"
        assert json.loads(path.read_text(encoding="utf-8")) == expected_schema


def test_namedtuple_instances_validate_against_schemas():
    for name in NAMEDTUPLE_NAMES:
        cls = getattr(data_sources, name)
        schema = json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))
        instance = _as_json(_sample_namedtuple(cls))
        jsonschema.Draft7Validator.check_schema(schema)
        jsonschema.validate(instance=instance, schema=schema)
