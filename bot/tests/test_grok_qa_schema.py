"""Contract tests for Grok structured QA fact JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

import qa


SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
QA_FACT_SCHEMA_PATH = SCHEMA_DIR / "qa_fact.json"


@pytest.fixture(scope="module")
def qa_fact_schema():
    return json.loads(QA_FACT_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_qa_fact_schema_valid(qa_fact_schema):
    jsonschema.Draft7Validator.check_schema(qa_fact_schema)


def test_allowed_buildings_match_schema(qa_fact_schema):
    assert set(qa_fact_schema["properties"]["building"]["enum"]) == set(qa.ALLOWED_BUILDINGS)


def test_allowed_categories_match_schema(qa_fact_schema):
    assert set(qa_fact_schema["properties"]["category"]["enum"]) == set(qa.ALLOWED_CATEGORIES)


def test_prompt_contains_same_enums():
    prompt = qa._build_qa_prompt("текст")

    for building in qa.ALLOWED_BUILDINGS:
        assert building in prompt
    for category in qa.ALLOWED_CATEGORIES:
        assert category in prompt


def test_valid_fact_validates(qa_fact_schema):
    fact = {
        "building": "АБК",
        "category": "бетонирование",
        "fact": "бетонирование фундамента",
    }

    jsonschema.validate(instance=fact, schema=qa_fact_schema)


def test_invalid_building_rejected(qa_fact_schema):
    fact = {
        "building": "Небоскрёб",
        "category": "бетонирование",
        "fact": "бетонирование фундамента",
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=fact, schema=qa_fact_schema)
