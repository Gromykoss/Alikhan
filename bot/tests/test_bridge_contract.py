"""Smoke tests for the Hermes WhatsApp Bridge OpenAPI contract."""

from __future__ import annotations

import json
from pathlib import Path

import requests


BRIDGE_URL = "http://127.0.0.1:3000"
PRODUCTION_GID = "120363400682390076@g.us"
OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "bridge_openapi.json"
TIMEOUT = 5


def _request(method, path, **kwargs):
    try:
        return requests.request(method, f"{BRIDGE_URL}{path}", timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise AssertionError(
            f"Bridge недоступен: {method} {BRIDGE_URL}{path} failed: {exc}"
        ) from exc


def test_bridge_health_matches_openapi():
    resp = _request("GET", "/health")

    assert resp.status_code == 200, f"/health HTTP {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    for field in ("status", "queueLength", "uptime", "scriptHash", "sendReadReceipts"):
        assert field in data, f"/health не вернул поле {field}: {data}"
    assert data["status"] == "connected", f"/health status={data['status']!r}, ожидалось connected"


def test_bridge_messages_endpoint():
    resp = _request("GET", "/messages", params={"only": PRODUCTION_GID})

    assert resp.status_code == 200, f"/messages HTTP {resp.status_code}: {resp.text[:300]}"
    assert isinstance(resp.json(), list), f"/messages должен вернуть JSON list: {resp.text[:300]}"


def test_bridge_ack_endpoint():
    resp = _request("POST", "/messages-ack", json={"messageIds": []})

    assert resp.status_code != 404, "/messages-ack отсутствует: bridge не соответствует A+ contract"


def test_bridge_collect_messages_dead():
    resp = _request("GET", "/collect-messages", params={"only": PRODUCTION_GID})

    assert resp.status_code == 404, f"/collect-messages должен быть dead 404, получил {resp.status_code}"


def test_bridge_openapi_valid():
    data = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    assert "paths" in data and data["paths"], "OpenAPI не содержит paths"
    assert "components" in data and data["components"], "OpenAPI не содержит components"
