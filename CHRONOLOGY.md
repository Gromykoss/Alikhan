# CHRONOLOGY — Хронология изменений Алихан бота

## 17.07.2026 (10:00) — Фикс фото: _media + Grok vision description

### Достигнуто
- **Фото обнаружение:** `imageMessage` (Evolution API) → `_media.mediaType == "image"` (Bridge) — песочница + прод
- **Vision-описание:** Grok (grok-4-latest) анализирует фото и пишет 1-2 предложения в `tags->>'description'`
- **Промпт:** описание состояния конструкций без предположения активных работ

### Баги исправлены
- Фото не сохранялись после миграции на Hermes Bridge (wrapper кладёт _media, код искал imageMessage)
- Дубль: Codex оставил `has_media = bool(msg...)` до определения `msg` → `[LOOP ERR] name 'msg' is not defined`

### Файлы
- `bot/main_waha.py` — строки 390-413 (prod), 526-576 (sandbox): фото + vision
- `bot/bridge_wrapper.py` — без изменений (debug Codex откачен)

### Коммиты
- `8a2a87e` — Fix: imageMessage→_media for bridge photo detection
- `aedc853` — fix: photo detection via _media + Grok vision description

## 16.07.2026 (19:30) — ЕЖО v4: N=100%, планы из сырых сообщений, оформление 3-го листа

### Достигнуто
- N = 100% (L = M) всегда
- U = O − P, O > 0 ∧ U > 0 → строка видна
- Планы парсятся из сырых сообщений через Grok-фолбек
- 3-й лист «Персонал» оформлен
- Фаза 8 скрыта целиком
- 76 строк открыто

### Коммит
- `86d8439` — Alikhan v4 final

## 15.07.2026 — Миграция на Hermes Bridge

### Ключевое изменение
Evolution API заменён на Hermes WhatsApp Bridge (:3000).
- `bridge_wrapper.py` — monkey-patch: перехватывает `requests.post` к Evolution API → Bridge API
- `main_waha.py` — не менялся, импортирует `from bridge_wrapper import *`
- Evolution API Docker — остановлен
- `alikhan.service` — остановлен

### Навыки созданы
- `alikhan-poll` — цикл опроса прорабов
- `alikhan-fill-ejo` — заполнение шаблона ЕЖО
- `alikhan-template-handoff` — цикл «бот→ручная правка→шаблон»
- `alikhan-monthly-template` — месячный план через «раскрой отчет»
