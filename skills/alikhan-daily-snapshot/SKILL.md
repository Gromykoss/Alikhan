---
name: alikhan-daily-snapshot
description: Ежедневный снимок дня для ТЗРК Джеруй. Собирает фото, сообщения, документы, QA, ЕЖО и погоду. Нарратив через Ollama (qwen2.5:7b), xAI только для vision. Только по запросу.
category: alikhan
---

# Alikhan Daily Snapshot — снимок дня

## Триггер

«снимок дня», «итоги дня», «сводка дня», «дайджест» — в песочнице.

## Архитектура — разделение движков (17.07.2026)

| Движок | Для чего | Почему |
|--------|----------|--------|
| **xAI (Grok)** | Только vision — описание фото | Нужно понимание изображений |
| **Ollama (qwen2.5:7b)** | Нарратив снимка дня | Локально, бесплатно, хватает |

**Правило:** xAI токены не тратятся на текстовые задачи. `ask_ollama()` для снимка, `ask_grok_raw()` только для фото.

## Что собирает

Данные за день с 00:01 по Бишкеку (UTC+6). **v5 (18.07.2026) — источники обновлены на OJR-таблицы:**

| Источник | Таблица/поле | Лимит | Примечание |
|----------|-------------|-------|------------|
| 📷 Фото | `ojr_photo_log` + `bot_memory_messages.tags` | 10 (все) | RAW — в результат напрямую. Если нет описания → `file_name` или `фото {id}` |
| 💬 Сообщения | `bot_memory_messages.content` | 8 | С отправителями |
| 📄 Документы | `COALESCE(file_name, tags->>'file_name')` | 5 | file_name может быть NULL |
| ✅ QA-факты | `ojr_section3_work_log` + `ojr_section1_personnel` | 10 | Через `get_daily_works()` + `get_daily_personnel()` |
| 📊 Работы | `ojr_section3_work_log` | 20 кодов | Через `get_daily_works()`. Код + название из шаблона ЕЖО. Формат: факт → план. |
| 🌤 Погода | `ojr_weather` + Open-Meteo fallback | — | Через `get_daily_weather()`. temp, desc, wind |

## Хранение

`ojr_daily_summary`: сводные показатели за день. **Обязательно `title_id`** (NOT NULL).

## Промпт — критичные правила (v3, 17.07.2026)

1. **Фото RAW — не через LLM.** `photo_block` собирается из БД и вставляется в результат напрямую. Ollama получает ТОЛЬКО сообщения + работы + QA. Это предотвращает реинтерпретацию описаний Grok'ом («установлены колонны» → «монтаж металлокаркаса»).
2. **Не смешивать источники.** Фото и QA — разные источники. Поскольку фото идут напрямую, а работы через Ollama, противоречий не возникает.
3. **Названия работ из ЕЖО.** Коды без названий бесполезны. `load_workbook('ЕЖО_шаблон.xlsx')`, колонка C (код) → колонка D (название). Формат: `2.1.5 (Разработка грунта) = 45.0`.
4. **Факт перед планом.** Порядок: `факт=X → план=Y`. Не наоборот.
5. **Только выполненные работы.** Не писать «бетонирование не выполнялось, монтаж не выполнялся...». Только то что ДЕЛАЛИ. Если ничего — «работы не проводились».
6. **Погода на русском.** `wttr.in?...format=j1&lang=ru`. Ключ `weatherDesc[0].value` (не `lang_ru`).
7. **4 блока строго:** 📷 Фото (из БД) / 📄 Документы / 💬 Сообщения / 📊 Работы
8. **Без выводов и оценок.** Только сухие факты.

## Timezone pitfall

Бишкек UTC+6. 00:01 Бишкек = 18:01 UTC предыдущего дня. **Никогда не использовать `created_at::date = %s`** — это UTC-день.

```python
from datetime import timedelta
bishkek_start = datetime(today.year, today.month, today.day, 0, 1) - timedelta(hours=6)
bishkek_end = bishkek_start + timedelta(days=1)
# WHERE created_at >= bishkek_start AND created_at < bishkek_end
```

## Ключевые файлы

- `bot/main_waha.py` — `generate_daily_snapshot()` + обработчик команды
- `bot/handlers.py` — `ask_ollama()` (timeout 30s, fallback → `ask_grok_raw`)
- `references/code-skeleton.md` — паттерны кода со всеми None-гардами (weather, pdata, mid, return)

## Проверка

```bash
# Логи
tail -f /home/hermes-workspace/Alikhan-migration/bot/bot.log | grep SNAPSHOT
# БД
psql evolution_db -c "SELECT fact FROM bot_memory_facts WHERE category='снимок_дня' ORDER BY created_at DESC LIMIT 1"
```

## Pitfalls

- **Missing `return result`** — самая частая причина краша `NoneType object is not subscriptable`. Функция строит `result` в последней строке, но забывает `return result`. `send_msg` получает `None` и падает на `text[:3800]`. После любого изменения функции — проверь что есть `return`.
- **Ollama model mismatch** — `handlers.py::OLLAMA_MODEL` должен совпадать с `ollama list`. Если в коде `qwen2.5:14b` а установлен `qwen2.5:7b`, Ollama молча фейлится → fallback на xAI → токены тратятся зря. Проверять: `grep OLLAMA_MODEL handlers.py && ollama list | grep qwen`.
- **`pdata` is None** — `poll['data']` может быть NULL в `bot_poll_state`. Код `pdata.get('poll', {}).get('status', '?')` на None → `AttributeError`. Гард: `if isinstance(pdata, dict) else "опрос не проводился"`.
- **`r['mid']` (content) is None** — для image-сообщений колонка `content` может быть NULL (даже при `tags IS NOT NULL`). `r['mid'][:8]` → `TypeError: 'NoneType' object is not subscriptable`. Используй `r.get('mid')` с fallback `"фото (без ID)"`.
- **Weather: `weatherDesc`, не `lang_ru`** — несмотря на `lang=ru`, ключ `lang_ru` может отсутствовать или быть `null`. Правильный путь: `wd = c.get('weatherDesc') or [{}]; desc = wd[0].get('value', '') if wd else ''`. Также `current_condition` может быть `null` → гард: `current = data.get('current_condition') or [{}]; c = current[0] if current else {}`.
- **Ollama timeout 30s** — если не уложился, автоматический fallback на xAI через `ask_ollama`
- **chat_id обязателен** в INSERT — иначе NOT NULL constraint violation
- **Не перегонять фото повторно** — описания уже в БД, бери `tags->>'description'`
- **Не использовать ask_grok** без image_base64 — уходит в Ollama (90s), используй `ask_ollama` напрямую
- **Погода на английском** — всегда `lang=ru` в URL wttr.in, ключ `weatherDesc[0].value`
- **Коды без названий** — `2.1.5 = 45.0` бесполезно. Всегда `load_workbook` для code→name
- **«Не выполнялось»** — не перечислять все типы работ которые НЕ делались. Только сделанное.
- **Фото через LLM** — Ollama реинтерпретирует описания Grok'а. Фото ТОЛЬКО сырыми из БД.
- **Документы пропадают** — `file_name` может быть NULL, используй `COALESCE(file_name, tags->>'file_name')`
- **Прод-фото без описаний** — если `tags->>'description'` IS NULL, падай на `tags->>'file_name'` или `фото {mid}`

## Структурированный промпт v2 (17.07.2026)

Новый промпт с 10 жёсткими правилами и примером целевого результата. В отличие от текущего промпта в `generate_daily_snapshot()` (стр. 181-210), форматит нарратив строго по правилам, не допуская реинтерпретации фото и смешивания источников.

Файлы в `bot/prompts/`:

| Файл | Назначение |
|------|------------|
| `daily_snapshot_prompt.md` | Шаблон промпта с 6 плейсхолдерами: `{weather}`, `{photo_block}`, `{doc_block}`, `{msg_block}`, `{poll_block}`, `{fact_block}`. ~1200 токенов с данными. |
| `gather_snapshot_data.py` | Python-скрипт: сбор данных (DB + wttr.in + шаблон ЕЖО) → рендеринг промпта. `--save` сохраняет в `/tmp/snapshot_prompt.txt`, `--raw` выдаёт JSON. |
| `prompts/README.md` | Руководство: варианты использования (Codex CLI, Grok Build, прямая интеграция, xAI), чеклист проверки, интеграция в cron. |

**Использование с Codex CLI:**
```bash
python3 bot/prompts/gather_snapshot_data.py --save
codex exec --dangerously-bypass-approvals-and-sandbox "$(cat /tmp/snapshot_prompt.txt)"
```

**Интеграция в `generate_daily_snapshot()`:** заменить строки 181-213 на рендеринг шаблона + `ask_ollama(template, max_tokens=700)`.

## Pitfalls — качество данных при сборе (тест 17.07.2026)

При тестовом прогоне `gather_snapshot_data.py --raw` обнаружены проблемы:

- **`bot_poll_state.data` — колонки нет в схеме.** Таблица имеет только `id, chat_id, poll_date, status, started_at, closed_at`. Фактические данные опроса хранятся в `bot_poll_residuals` (колонки: `poll_id, code, name, building, actual_today, plan_volume, residual_volume`). Запрос `SELECT data FROM bot_poll_state` гарантированно падает. Правильный запрос: JOIN `bot_poll_residuals r ON r.poll_id = s.id WHERE s.chat_id=%s AND s.poll_date=%s`. **Исправлено 17.07.2026.**
- **QA-факты с негативными записями.** «Бетонирование не выполнялось», «Монтаж не выполнялся» попадают в `fact_block`. Фильтр: `AND fact NOT ILIKE '%не выполня%'`.
- **Фото без тега `building`.** `tags->>'building'` IS NULL → в выдаче «без тег». Данные из ранних версий (до 15.07). В проде тег заполняется при сохранении фото.
- **wttr.in недоступен.** fallback на Open-Meteo реализован в `generate_daily_snapshot()` и `gather_snapshot_data.py` (17.07.2026).

## Связанное

- `alikhan-photo-vision` — описание отдельных фото через xAI
- `alikhan-poll-logic` — данные опроса для раздела 📊 Работы
- `alikhan-fill-ejo` — объёмы из ЕЖО

## Коррекции пользователя (17.07.2026)

Сергей ожидает что Hermes САМ найдёт ошибки в выдаче до того как он укажет. После показа снимка — сначала мой разбор багов, потом его дополнения.

**Автономность операций:** Не спрашивать подтверждения на перезапуск бота, применение фиксов, запуск моста и другие рутинные действия. Пользователь явно требует «перезапусти бота сам» и раздражается на вопросы «делать?». После нахождения бага — фиксить и перезапускать без лишних вопросов.

Критичные требования к формату:
- Погода на русском. «Sunny» → недопустимо.
- Коды работ с названиями. «2.1.5 = 45.0» без названия работы → пользователь не помнит 800+ кодов ЕЖО.
- Факт перед планом. Порядок: что сделали → что планируют.
- Только плановые/выполненные работы. Не перечислять чего НЕ делали.
- Описания фото не должны реинтерпретироваться. «Установлены колонны» не должно превращаться в «монтаж металлокаркаса».
