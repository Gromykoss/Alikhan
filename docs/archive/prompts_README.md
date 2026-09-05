# Daily Snapshot Prompt — Рекомендации по использованию
# Версия: v2, 17.07.2026

## Что делает

Промпт `daily_snapshot_prompt.md` + скрипт `gather_snapshot_data.py` заменяют вызов `ask_ollama()` внутри
`generate_daily_snapshot()`. Вместо одного LLM-вызова с 700 токенами, данные собираются отдельно,
нарратив генерируется отдельно.

## Архитектура

```
┌─────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│ gather_snapshot_    │────▶│ daily_snapshot_prompt│────▶│ Codex CLI /          │
│ data.py             │     │ .md (с данными)      │     │ Grok Build CLI       │
│ (DB + weather +     │     │                      │     │ (генерирует нарратив)│
│  template)          │     │                      │     │                      │
└─────────────────────┘     └──────────────────────┘     └────────┬─────────────┘
                                                                  │
                                                                  ▼
                                                         ┌──────────────────────┐
                                                         │ Сборка результата:   │
                                                         │ 📅 Дата + 🌤 Погода  │
                                                         │ + 📷 Фото (RAW)      │
                                                         │ + 📄 Документы       │
                                                         │ + нарратив от LLM    │
                                                         └──────────────────────┘
```

**Ключевое отличие от текущего кода:** фото НЕ передаются в LLM для нарратива.
Они вставляются в результат напрямую из БД. LLM получает только:
- Сообщения группы
- Данные ЕЖО / опроса
- QA-факты
- Погоду

## Варианты использования

### Вариант A: Codex CLI (gpt-5.5, v0.140.0)

```bash
# 1. Собрать данные и сохранить промпт в файл
python3 /home/hermes-workspace/Alikhan-migration/bot/prompts/gather_snapshot_data.py \
  --save --date 2026-07-17

# 2. Передать промпт в Codex CLI
cd /home/hermes-workspace/Alikhan-migration
codex exec --dangerously-bypass-approvals-and-sandbox "$(cat /tmp/snapshot_prompt.txt)"
```

**Плюсы:**
- Codex CLI доступен на VPS, работает без PTY (в отличие от Grok Build)
- `--dangerously-bypass-approvals-and-sandbox` пропускает sandbox (не работает на этой VPS)
- Модель gpt-5.5 даёт качественный нарратив

**Минусы:**
- Код в промпте → Codex может попытаться «помочь» и написать код вместо генерации текста
- Нужно следить чтобы не ушёл в режим редактирования файлов

### Вариант Б: Grok Build CLI (v0.2.59)

```bash
# 1. Собрать данные
python3 /home/hermes-workspace/Alikhan-migration/bot/prompts/gather_snapshot_data.py \
  --save --date 2026-07-17

# 2. Передать в Grok Build (ТРЕБУЕТ PTY!)
terminal(pty=true, timeout=120)
  command: grok --yolo "$(cat /tmp/snapshot_prompt.txt)"
```

**Плюсы:**
- xAI Grok — тот же провайдер что используется для vision, знает контекст Джеруя
- `--yolo` авто-одобряет все действия

**Минусы:**
- Требует PTY — нельзя запустить просто `terminal("grok ...")`, упадёт с exit code 1
- OIDC-авторизация может истечь

### Вариант В: Прямая интеграция с generate_daily_snapshot()

Модифицировать `main_waha.py::generate_daily_snapshot()` — заменить вызов `ask_ollama()` на:

```python
# Собрать данные
data = {
    "weather": weather,
    "photo_block": photo_block,
    "doc_block": doc_block,
    "msg_block": msg_block,
    "poll_block": poll_info if poll_info else "опрос не проводился",
    "fact_block": fact_block,
}

# Рендерить промпт
from pathlib import Path
template = (Path(__file__).parent / "prompts" / "daily_snapshot_prompt.md").read_text(encoding="utf-8")
for key, val in data.items():
    template = template.replace("{" + key + "}", val)

# Передать в Ollama (оставляем ask_ollama, но с новым промптом)
from handlers import ask_ollama
narrative = ask_ollama(template, max_tokens=700)
```

Это минимальное изменение — сохраняет ask_ollama() как движок, но использует улучшенный промпт.

### Вариант Г: xAI напрямую (пропустить Ollama)

Для максимального качества пожертвовать экономией токенов:

```python
from handlers import ask_grok_raw
narrative = ask_grok_raw(template, max_tokens=700)
```

**⚠️ Затраты:** ~500 токенов xAI на один снимок. При ежедневном использовании — ~15K/мес.

## Как избежать повторов и мусора

Главный источник проблем в текущем промпте (v1, строка 181-210 main_waha.py):
1. **Фото идут в LLM** → Grok/Ollama реинтерпретирует описания («установлены колонны» → «монтаж металлокаркаса»)
2. **QA-факты дублируют ЕЖО** → «1 экскаватор» из QA и «экскаватор» из ЕЖО = двойной счёт
3. **Нет жёсткого разделения блоков** → нарратив смешивает источники

**Решение в новом промпте:**
- Правило 2: фото RAW — не через LLM
- Правило 8: без повторов между блоками
- Правило 5: факт строго перед планом
- Правило 1: 4 блока строго, без смешивания

## Проверка качества

### Тестовый прогон

```bash
# 1. Собрать данные
python3 /home/hermes-workspace/Alikhan-migration/bot/prompts/gather_snapshot_data.py \
  --save --chat-id 120363179621030401@g.us

# 2. Проверить промпт
cat /tmp/snapshot_prompt.txt | head -20   # убедиться что данные подставлены

# 3. Прогнать через Codex
codex exec --dangerously-bypass-approvals-and-sandbox "$(cat /tmp/snapshot_prompt.txt)"

# 4. Проверить результат на соответствие правилам
```

### Чеклист проверки

- [ ] Ровно 4 блока + Итог
- [ ] Фото не реинтерпретированы (сверить с сырыми описаниями из БД)
- [ ] Коды работ с названиями из шаблона
- [ ] Факт перед планом (не наоборот)
- [ ] Нет «не выполнялось»
- [ ] Нет оценочных слов (хорошо, отлично, слабо, прогресс)
- [ ] Нет рекомендаций (следует, необходимо, рекомендуется)
- [ ] Погода на русском
- [ ] Нет дублирования между блоками
- [ ] Каждый блок не пустой (если пустой — помечен)

## Интеграция в CI/автоматизацию

```bash
# В cron (ежедневно 18:00 Бишкек = 12:00 UTC)
0 12 * * * cd /home/hermes-workspace/Alikhan-migration/bot && \
  python3 prompts/gather_snapshot_data.py --save && \
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat /tmp/snapshot_prompt.txt)" \
  > /tmp/snapshot_result.txt 2>&1
```

## Pitfalls

1. **Codex CLI пытается писать код.** Если промпт длинный и структурированный, Codex может воспринять его как задачу на программирование и начать генерировать Python вместо нарратива. Решение: добавить в начало промпта явную инструкцию «НЕ пиши код, только текст».

2. **Grok Build без PTY.** `grok --yolo` без PTY падает с `exit code 1`. Всегда использовать `terminal(pty=true)` или запускать в shell с `script -q -c`.

3. **Ошибки в данных.** Если в БД нет фото/сообщений/фактов, блоки заполняются «нет». Это нормально — LLM получит пустые блоки и должен вывести их с пометкой.

4. **Большие промпты.** При 10 фото × 120 символов + 8 сообщений × 100 символов + 10 фактов × 100 символов + 20 позиций ЕЖО × 60 символов + правила (~4000 символов) ≈ 8000 символов ≈ 2000 токенов. В пределах контекстного окна qwen2.5:7b (32K).

5. **chat_id в poll.** По умолчанию gather_snapshot_data.py использует песочницу. Для прода нужно передать `--chat-id 120363400682390076@g.us`.
