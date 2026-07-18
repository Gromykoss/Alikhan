---
name: alikhan-photo-vision
description: Автоматическое описание фото строительной площадки через Grok vision API. Фото из WhatsApp сохраняются в БД с тегом здания и текстовым описанием от Grok.
category: alikhan
---

# Alikhan Photo Vision — автоматическое описание фото через Grok

## Триггер
Любое фото в WhatsApp-группе (песочница или прод).

## Поток
1. Hermes Bridge получает фото → `extractBridgeEvent()` ставит `hasMedia: true, mediaType: "image"`
2. Wrapper (`bridge_wrapper.py`:89-96) прикрепляет `_media` к Evolution-совместимой записи
3. `main_waha.py` (строки 390/526) проверяет `msg.get("_media").get("mediaType") == "image"`
4. Сохраняет в `bot_memory_messages` с тегом здания из caption
5. Читает файл из `/tmp/hermes-media-cache/`, base64 → Grok vision
6. Обновляет `tags->>'description'` в БД
7. **Escalation (17.07.2026):** проверяет описание на speculative-слова. При обнаружении → ⚠️ в песочницу

## Escalation

Если Grok-описание содержит speculative-слова — бот шлёт предупреждение в песочницу:

| Паттерн | Пример | Сигнал |
|---------|--------|--------|
| предположител* | «Предположительно, монтаж...» | Low confidence |
| вероятн* / возможн* | «Вероятно, работы...» | Speculation |
| похож* / кажетс* | «Похоже на бетонирование» | Speculation |
| монтаж идёт/ведётся | «Монтаж металлокаркаса идёт» | Assumed activity |
| ведутся работы | «Ведутся кровельные работы» | Assumed activity |
| процесс* / активн* | «Активная фаза строительства» | Assumed activity |

Реализация: `main_waha.py` строки 579+ (commit 1515653, 17.07.2026).
Проверка: `tail -f /tmp/alikhan.log | grep -E "PHOTO DESC|PHOTO ESCALATE"`

## Ключевые файлы
- `bot/main_waha.py` — строки 390-413 (prod), 526-588 (sandbox + escalation)
- `bot/handlers.py` — `ask_grok_raw()` с `image_base64`
- `bot/bridge_wrapper.py` — monkey-patch Evolution→Bridge

## Промпт для Grok
"Опиши что видно на фото строительной площадки: состояние конструкций, наличие техники, материалов, людей. Не предполагай что работы ведутся — опиши только наблюдаемое состояние. 1-2 предложения на русском."

## Формат в БД
```json
{
  "building": "АБК",
  "msg_id": "3AF6DF645B62...",
  "description": "На фото видна большая крытая конструкция..."
}
```

## Проверка
```bash
tail -f /tmp/bot.log | grep "PHOTO DESC"
```

## Правило движков (17.07.2026)

**xAI только для vision.** Для текстовых задач (снимок дня, ответы на вопросы) — Ollama (qwen3:8b). Экономия токенов xAI. `ask_grok_raw` вызывается только с `image_base64`.

## Связанное
- **Daily Snapshot:** `references/daily-snapshot.md` — агрегация всех данных дня. Timezone: Бишкек UTC+6. Нарратив через Ollama.
- **Daily Snapshot skill:** `alikhan-daily-snapshot` — полное руководство по снимку дня
