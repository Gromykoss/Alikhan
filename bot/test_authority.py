#!/usr/bin/env python3
"""Unit tests for Alikhan authority guards."""

import os
import sys

import pytest


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from authority import (  # noqa: E402
    BUZZ_SEND_SCRIPT,
    PRODUCTION_CHAT_ID,
    SANDBOX_CHAT_ID,
    AuthorityLevel,
    _buzz_send_allowed,
    can_send,
    guard_tool_call,
    is_mutation_allowed,
)


def _buzz_command(*args: str) -> str:
    return " ".join(("/usr/bin/python3", str(BUZZ_SEND_SCRIPT), *args))


@pytest.mark.scenario("agent-routing-safety.can_send_fail_closed")
def test_can_send_fail_closed():
    assert can_send(SANDBOX_CHAT_ID, "operator") is True
    assert can_send(PRODUCTION_CHAT_ID, "operator") is False
    assert can_send(PRODUCTION_CHAT_ID, "operator", "tok") is True
    assert can_send("unknown@g.us", "operator") is False
    assert can_send(PRODUCTION_CHAT_ID, "operator", None) is False
    assert can_send(PRODUCTION_CHAT_ID, "operator", "") is False


@pytest.mark.scenario("agent-routing-safety.is_mutation_allowed_matrix")
def test_is_mutation_allowed_matrix():
    assert is_mutation_allowed(AuthorityLevel.READ, actor_is_orchestrator=True) is True
    assert is_mutation_allowed(AuthorityLevel.ANALYZE, actor_is_orchestrator=True) is True
    assert is_mutation_allowed(AuthorityLevel.LOCAL, actor_is_orchestrator=True) is False

    orchestrator_allowed = {AuthorityLevel.READ, AuthorityLevel.ANALYZE}
    for level in AuthorityLevel:
        assert (
            is_mutation_allowed(level, actor_is_orchestrator=True)
            is (level in orchestrator_allowed)
        )

    operator_allowed = {
        AuthorityLevel.READ,
        AuthorityLevel.ANALYZE,
        AuthorityLevel.LOCAL,
    }
    for level in AuthorityLevel:
        assert (
            is_mutation_allowed(level, actor_is_orchestrator=False)
            is (level in operator_allowed)
        )


@pytest.mark.scenario("agent-routing-safety.buzz_send_argv_canon")
def test_buzz_send_argv_canon():
    assert _buzz_send_allowed(_buzz_command("--as", "alikhan", "--to", "hermes", "hi")) is True
    assert _buzz_send_allowed(_buzz_command("--as=alikhan", "hi")) is False

    for command in (
        _buzz_command("--as", "alikhan", "hi;"),
        _buzz_command("--as", "alikhan", "hi", "|", "cat"),
        _buzz_command("--as", "alikhan", "hi", "&&", "cat"),
        _buzz_command("--as", "alikhan", "$(cat", "x)"),
    ):
        assert _buzz_send_allowed(command) is False

    assert _buzz_send_allowed("/usr/bin/python3") is False
    assert _buzz_send_allowed(_buzz_command("--as", "alikhan", "'unterminated")) is False


@pytest.mark.scenario("agent-routing-safety.guard_tool_call_file_boundary")
def test_guard_tool_call_file_boundary():
    assert guard_tool_call("write_file", {"path": "~/Alikhan-migration/bot/x.py"}) == (
        True,
        "",
    )
    allowed, message = guard_tool_call("write_file", {"path": "~/robot-man/x.py"})
    assert allowed is False
    assert "вне разрешённой зоны Alikhan" in message

    assert guard_tool_call("write_file", {"path": ""}) == (True, "")

    assert guard_tool_call(
        "write_file",
        {"a": {"path": "~/Alikhan-migration/bot/nested.py"}},
    ) == (True, "")
    allowed, message = guard_tool_call(
        "write_file",
        {"items": [{"path": "~/Alikhan-migration/bot/ok.py"}, [{"path": "~/robot-man/x.py"}]]},
    )
    assert allowed is False
    assert "вне разрешённой зоны Alikhan" in message

    assert guard_tool_call("foo", {"path": "~/robot-man/x.py"}) == (True, "")


@pytest.mark.scenario("agent-routing-safety.guard_terminal_fragments")
def test_guard_terminal_fragments():
    allowed, message = guard_tool_call("terminal", {"command": "ls ~/robot-man"})
    assert allowed is False
    assert "~/robot-man" in message

    allowed, message = guard_tool_call("terminal", {"command": "cat secrets.env"})
    assert allowed is False
    assert "secrets.env" in message

    allowed, message = guard_tool_call("terminal", {"command": ""})
    assert allowed is False
    assert "terminal.command пустой" in message

    assert guard_tool_call(
        "terminal",
        {"command": _buzz_command("--as", "alikhan", "--to", "hermes", "hi")},
    ) == (True, "")

    allowed, message = guard_tool_call("terminal", {"command": "echo buzz-send.py"})
    assert allowed is False
    assert "каноническим argv-вектором" in message

    assert guard_tool_call("terminal", {"command": "ls bot/"}) == (True, "")
