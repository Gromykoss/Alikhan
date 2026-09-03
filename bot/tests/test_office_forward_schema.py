import json
from pathlib import Path

import jsonschema
import pytest

import office_forward


SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "office_forward_payload.json"


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


@pytest.fixture
def payload_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _capture_payload(monkeypatch, text="как есть", topic="общее"):
    calls = []
    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook", "secret-key"),
    )

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return DummyResponse(202)

    ok = office_forward.forward_to_office(
        "chat-1",
        "msg-1",
        "foreman-1",
        text,
        topic,
        async_send=False,
        post=fake_post,
    )

    assert ok is True
    assert calls
    return calls[0]["json"]


def test_payload_schema_valid(payload_schema):
    jsonschema.Draft7Validator.check_schema(payload_schema)


def test_topics_match_code(payload_schema):
    assert set(payload_schema["properties"]["topic"]["enum"]) == set(office_forward.TOPICS)


def test_const_fields_match(payload_schema, monkeypatch):
    payload = _capture_payload(monkeypatch)

    assert payload_schema["properties"]["source"]["const"] == payload["source"] == "hermes"
    assert payload_schema["properties"]["platform"]["const"] == payload["platform"] == "whatsapp"
    jsonschema.validate(instance=payload, schema=payload_schema)


def test_real_payload_validates(payload_schema, monkeypatch):
    payload = _capture_payload(monkeypatch, text="Подскажите по кровле?", topic="кровля")

    jsonschema.validate(instance=payload, schema=payload_schema)


def test_text_truncated_contract(payload_schema, monkeypatch):
    payload = _capture_payload(monkeypatch, text="я" * (office_forward.MAX_TEXT_LEN + 10))

    assert office_forward.MAX_TEXT_LEN == payload_schema["properties"]["text"]["maxLength"]
    assert len(payload["text"]) == office_forward.MAX_TEXT_LEN
    jsonschema.validate(instance=payload, schema=payload_schema)


def test_invalid_topic_rejected(payload_schema):
    payload = {
        "source": "hermes",
        "platform": "whatsapp",
        "chat_id": "chat-1",
        "message_id": "msg-1",
        "from": "foreman-1",
        "text": "вопрос",
        "topic": "несуществующая",
        "reply_to": None,
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=payload_schema)
