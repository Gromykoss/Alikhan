# Poll Logic Redesign — 2026-07-16

## Исходная ситуация

Бот показывал опрос по хардкодным активным разделам, потом по БД `bot_schedule_phases`. Проблемы:
- Активные фазы из расписания не совпадают с реальностью (фаза 4 не начата, фаза 7 частично)
- `len(building) < 3` отсекал здания «НК», «НТ»
- Полный список из фазы слишком большой для WhatsApp
- Сообщение целиком не влезало в лимит WhatsApp (~3800 символов)

## Решение: Столбец O — источник истины

### Бизнес-логика
- В начале месяца: `Алихан раскрой отчет` — бот раскрывает все строки, присылает шаблон
- Сергей заполняет столбец O (месячный план) по нужным кодам
- Ежедневный опрос: бот показывает коды где col O > 0
- Остаток (col 21) — только для отображения, не фильтр

### Код
```python
# poll.py:_get_work_items_from_template()
monthly_plan = _safe_float(ws.cell(row=row, column=15).value)  # col O
ostatok = _safe_float(ws.cell(row=row, column=21).value)       # col U
# ...
if monthly_plan <= 0:
    continue
```

### Команда «Алихан раскрой отчет»
- Принимает триггеры: «раскрой отчет», «покажи все строки», «разверни отчет»
- Раскрывает все строки в шаблоне → отправляет файл
- Сообщает: «Заполните столбец O (месячный план) и пришлите обратно»

### Сообщение опроса — две части
- `header`: сводка QA (персонал, техника, фото, материалы, планы)
- `residuals`: список кодов работ, отдельным сообщением (влезает в WhatsApp)

### Что убрано
- ❌ Хардкод `ACTIVE_SECTIONS`
- ❌ Запросы `bot_schedule_phases` для фильтра
- ❌ Сложная логика «активные/просроченные/будущие»
- ❌ Фильтр `len(building) < 3` (отсекал НК, НТ)

### Что отключено
- `fill_ejo.py:_hide_rows()` — закомментирован. Все строки видны для месячного плана.

## Document Download via Hermes Bridge

### Проблема
Evolution API (:8080) остановлен. `urllib.request.Request(f"{EVO}/chat/getBase64FromMediaMessage/...")` не работает.

### Решение
- `bridge_wrapper.py`: передаёт `_media` метаданные (mediaUrls, fileName, hasMedia)
- `main_waha.py`: читает `msg['_media']`, загружает файл из локального кеша
- Bridge кеш: `/tmp/hermes-media-cache/` (через `HERMES_DOCUMENT_CACHE_DIR`)

### Запуск bridge с кешем
```bash
export HERMES_DOCUMENT_CACHE_DIR=/tmp/hermes-media-cache
export HERMES_IMAGE_CACHE_DIR=/tmp/hermes-media-cache
export HERMES_AUDIO_CACHE_DIR=/tmp/hermes-media-cache
node bridge.js --mode bot --session ~/.hermes/sessions/whatsapp &
```

### Код в bridge_wrapper.py
```python
if m.get("hasMedia"):
    media = {
        "mediaType": m.get("mediaType", ""),
        "mimetype": m.get("mime", ""),
        "fileName": m.get("fileName", ""),
        "mediaUrls": m.get("mediaUrls", []),
    }
    rec["message"]["_media"] = media
```

### Код в main_waha.py
```python
media_meta = msg.get("_media")
if media_meta and media_meta.get("mediaType") == "document":
    local_path = media_meta.get("mediaUrls", [None])[0]
    if local_path and os.path.exists(local_path):
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
```

## User Corrections (2026-07-16)

1. **«Не выдумывай новые формы»** — работать ТОЛЬКО с существующим шаблоном `ЕЖО_шаблон.xlsx`. Не создавать новых Excel-файлов с изменённой структурой («План_на_месяц.xlsx»). Пользователь работает с оригиналом.
2. **«Раскрой все строки и пришли»** — бот должен уметь раскрывать скрытые строки и отправлять полный отчёт одной командой
3. **«Столбец O — план на месяц»** — этот столбец определяет что в опросе, не расписание и не остатки
4. **«Бизнеслогика хромает»** — не гадать какие разделы активны по расписанию, использовать явный план (столбец O)
5. **«Нельзя туда -сюда откатывать, нужно проработать логику»** — прежде чем патчить, продумать логику до конца. Не делать итеративные правки без согласованного плана
6. **«зачем ты изменил форму»** — не менять структуру документа при отправке пользователю. Раскрыть строки в оригинальном шаблоне, не создавать копию с другой структурой
7. **«0 и отрицательным остатком»** — коды с O>0 но остатком ≤0 НЕ должны быть в опросе. Добавлен filter `if ostatok <= 0: continue`
8. **«сообщение не влезло»** — разбить опрос на header + residuals двумя сообщениями под лимит WhatsApp
