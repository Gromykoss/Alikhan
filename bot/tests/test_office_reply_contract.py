from pathlib import Path

import yaml


OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "office_reply_openapi.yaml"
WEBHOOK_PATH = "/p/alikhan/webhooks/office-reply"


def _load_openapi():
    return yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


def test_openapi_valid():
    spec = _load_openapi()
    post = spec["paths"][WEBHOOK_PATH]["post"]

    assert spec["openapi"] == "3.0.3"
    assert "HMAC" in spec["components"]["securitySchemes"]
    assert set(post["responses"]) >= {"202", "401", "400"}


def test_hmac_required():
    spec = _load_openapi()
    security = spec["paths"][WEBHOOK_PATH]["post"]["security"]

    assert {"HMAC": []} in security
    assert security != []


def test_human_gate_documented():
    spec = _load_openapi()
    post = spec["paths"][WEBHOOK_PATH]["post"]
    combined_text = " ".join(
        [
            post.get("description", ""),
            post["responses"]["202"].get("description", ""),
        ]
    )

    assert "Human Gate" in combined_text
