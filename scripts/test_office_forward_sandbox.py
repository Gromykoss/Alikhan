#!/usr/bin/env python3
"""Send sandbox office-forward webhook probes without touching production WhatsApp."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_DIR = os.path.join(ROOT, "bot")
sys.path.insert(0, BOT_DIR)

from config import SANDBOX
from office_forward import classify_office_question, forward_to_office, get_last_http_status

QUESTIONS = [
    "Подскажите, когда офис согласует кровлю АБК?",
    "Можно ли завтра начинать фасадные откосы общежития?",
    "Нужна арматура 12, кто подтвердит поставку?",
    "Какая расценка в смете на дополнительный объем?",
]


def main() -> int:
    if SANDBOX != "120363179621030401@g.us":
        print(f"ABORT: unexpected SANDBOX={SANDBOX}")
        return 2

    for idx, text in enumerate(QUESTIONS, start=1):
        topic = classify_office_question(text)
        if not topic:
            print(f"{idx}. skip: not an office question")
            continue
        ok = forward_to_office(
            chat_id=SANDBOX,
            message_id=f"sandbox-office-forward-{idx}",
            sender="sandbox-test",
            text=text,
            topic=topic,
            async_send=False,
        )
        print(f"{idx}. topic={topic} status={get_last_http_status()} ok={ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
