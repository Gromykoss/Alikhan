import os
import sys
import threading
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import office_forward


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def test_classify_roof_question():
    assert office_forward.classify_office_question("Подскажите, когда закрываем кровлю АБК?") == "кровля"


def test_classify_facade_question():
    assert office_forward.classify_office_question("Можно ли завтра начинать фасад и наружные откосы?") == "наружка"


def test_classify_materials_question():
    assert office_forward.classify_office_question("Нужна арматура 12, кто подтвердит поставку?") == "материалы"


def test_classify_estimate_question():
    assert office_forward.classify_office_question("Какая расценка в смете на этот объем?") == "смета"


def test_topic_keyword_uses_word_boundary_for_act():
    assert office_forward.classify_office_question("Факт по объему подтвердите?") == "общее"
    assert office_forward.classify_office_question("Акт кто проверит?") == "смета"


def test_question_with_equals_is_not_suppressed_as_qa_fact():
    assert office_forward.classify_office_question("Объём=12?") == "общее"


def test_classify_general_question():
    assert office_forward.classify_office_question("Кто согласует проход сегодня?") == "общее"


def test_skip_qa_fact():
    assert office_forward.classify_office_question("Айбикон рабочие 7 ИТР 3") is None


def test_skip_poll_reply():
    assert office_forward.classify_office_question("2.1.5 = 12 м3") is None


def test_skip_bot_command():
    assert office_forward.classify_office_question("Алихан статус опроса?") is None


def test_skip_substring_question_markers():
    assert office_forward.classify_office_question("никто не выходил") is None


def test_skip_unaddressed_bot_command():
    assert office_forward.classify_office_question("ежо?") is None


def test_skip_qa_fact_with_question_marker_word():
    assert office_forward.classify_office_question("как обычно рабочие 7") is None


def test_plain_tonnage_does_not_create_poll_reply():
    assert office_forward.classify_office_question("25т") is None


def test_forward_to_office_posts_payload(monkeypatch):
    calls = []

    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook", "secret-key"),
    )

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return DummyResponse(200)

    ok = office_forward.forward_to_office(
        "chat",
        "msg-1",
        "sender",
        "как есть",
        "общее",
        async_send=False,
        post=fake_post,
    )

    assert ok is True
    assert calls == [
        {
            "url": "https://office.example/webhook",
            "json": {
                "source": "hermes",
                "platform": "whatsapp",
                "chat_id": "chat",
                "message_id": "msg-1",
                "from": "sender",
                "text": "как есть",
                "topic": "общее",
                "reply_to": None,
            },
            "headers": {"Authorization": "Bearer secret-key"},
            "timeout": 10,
        }
    ]


def test_async_send_joins_before_return(monkeypatch):
    calls = []
    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook", "secret-key"),
    )

    def fake_post(url, json, headers, timeout):
        calls.append(json["message_id"])
        return DummyResponse(204)

    ok = office_forward.forward_to_office(
        "chat",
        "msg-daemon",
        "sender",
        "кто согласует?",
        "общее",
        post=fake_post,
    )

    assert ok is True
    assert calls == ["msg-daemon"]


def test_async_timeout_leaves_no_daemon_office_forward_thread(monkeypatch):
    logs = []
    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook", "secret-key"),
    )

    def slow_post(url, json, headers, timeout):
        time.sleep(0.05)
        return DummyResponse(204)

    ok = office_forward.forward_to_office(
        "chat",
        "msg-slow",
        "sender",
        "кто согласует?",
        "общее",
        post=slow_post,
        log_func=logs.append,
        join_timeout=0.01,
    )

    assert ok is False
    assert logs == ["OFFICE_FORWARD timeout message_id=msg-slow"]
    for thread in threading.enumerate():
        assert not (thread.name == "office-forward" and thread.daemon)


def test_non_2xx_retries_and_logs(monkeypatch):
    statuses = [500, 200]
    logs = []
    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook?token=secret", "secret-key"),
    )

    def fake_post(url, json, headers, timeout):
        return DummyResponse(statuses.pop(0))

    ok = office_forward.forward_to_office(
        "chat",
        "msg-retry",
        "sender",
        "кто согласует?",
        "общее",
        async_send=False,
        post=fake_post,
        log_func=logs.append,
        retries=1,
    )

    assert ok is True
    assert len(statuses) == 0
    assert logs == ["OFFICE_FORWARD failed message_id=msg-retry status=500 attempt=1/2"]
    assert "token=" not in " ".join(logs)
    assert "secret-key" not in " ".join(logs)


def test_timeout_webhook_retries_and_logs_safely(monkeypatch):
    calls = []
    logs = []
    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook?token=secret", "secret-key"),
    )

    def fake_post(url, json, headers, timeout):
        calls.append(json["message_id"])
        raise requests.Timeout("https://office.example/webhook?token=secret timed out")

    ok = office_forward.forward_to_office(
        "chat",
        "msg-timeout",
        "sender",
        "кто согласует?",
        "общее",
        async_send=False,
        post=fake_post,
        log_func=logs.append,
        retries=1,
    )

    assert ok is False
    assert calls == ["msg-timeout", "msg-timeout"]
    assert logs == [
        "OFFICE_FORWARD error message_id=msg-timeout type=Timeout attempt=1/2",
        "OFFICE_FORWARD error message_id=msg-timeout type=Timeout attempt=2/2",
    ]
    assert "token=" not in " ".join(logs)
    assert "office.example" not in " ".join(logs)


def test_missing_secrets(monkeypatch):
    logs = []
    monkeypatch.setattr(office_forward, "_office_webhook_secrets", lambda: ("", ""))

    ok = office_forward.forward_to_office(
        "chat",
        "msg-no-secret",
        "sender",
        "кто согласует?",
        "общее",
        async_send=False,
        post=lambda **kwargs: DummyResponse(200),
        log_func=logs.append,
    )

    assert ok is False
    assert logs == ["OFFICE_FORWARD skipped: webhook config missing"]


def test_long_text_truncated_to_4000(monkeypatch):
    calls = []
    monkeypatch.setattr(
        office_forward,
        "_office_webhook_secrets",
        lambda: ("https://office.example/webhook", "secret-key"),
    )

    def fake_post(url, json, headers, timeout):
        calls.append(json)
        return DummyResponse(200)

    ok = office_forward.forward_to_office(
        "chat",
        "msg-long",
        "sender",
        "я" * 4100,
        "общее",
        async_send=False,
        post=fake_post,
    )

    assert ok is True
    assert len(calls[0]["text"]) == 4000
