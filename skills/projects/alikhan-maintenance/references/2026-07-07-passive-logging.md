# Passive Message Logging — Все сообщения в БД (2026-07-07)

**Требование:** «Алихан должен фиксировать все что происходит в группе все сообщения, но отвечать должен только когда к нему обратились».

## Implementation

```python
# В main_waha.py, строка 527 — ПЕРЕД вызовом route():
from db import save_message as _log_msg
_log_msg(SANDBOX, sender, "user", text)
```

Вызов `save_message()` происходит для КАЖДОГО текстового сообщения после прохождения guard:
- Не fromMe (не свои сообщения)
- Не в seen_ids (уже обработано)
- Не старше 10 минут
- Не пустой текст

QA-парсинг (персонал/техника/материалы) уже работал для всех сообщений через `router.py` (строка 20-23). Этот вызов добавляет сохранение plain-text сообщений, которые не содержат structured QA data.

## Ответ (reply)

Ответ управляется отдельно через router:
- QA → авто-подтверждение
- VOR-коды → RESIDUAL bypass (не требует «алихан»)
- Обращение по имени → Grok/DB/Weather/Schedule
- Остальное → IGNORE (сохраняется, но не отвечает)

## Date Extraction Fix (2026-07-07)

Файлы с 2-значным годом (`06.07.26`) не парсились regex'ом `\d{4}`.

```python
# main_waha.py, строка 121
m = _re.search(r'(\d{2})\.(\d{2})\.(\d{4})', fname)
if not m:
    m = _re.search(r'(\d{2})\.(\d{2})\.(\d{2})\b', fname)
    if m:
        date_str = f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"
```
