# Hermes Bridge — прием документов и кеширование

## Проблема (16.07.2026)

После миграции с Evolution API на Hermes Bridge бот перестал получать входящие документы (.xlsx). Старый код вызывал `http://127.0.0.1:8080/chat/getBase64FromMediaMessage/alikhan` (Evolution API), который был остановлен.

## Решение

### 1. Кеш-директории для медиа

Hermes Bridge автоматически скачивает входящие медиа через `downloadMediaMessage` из Baileys, но требует указания директорий через переменные окружения:

```bash
export HERMES_DOCUMENT_CACHE_DIR=/tmp/hermes-media-cache
export HERMES_IMAGE_CACHE_DIR=/tmp/hermes-media-cache
export HERMES_AUDIO_CACHE_DIR=/tmp/hermes-media-cache
```

Без этих переменных `defaultWriteMediaFile` получает `dir=undefined` → `mkdirSync(undefined)` → ошибка → медиа не сохраняется.

### 2. Передача mediaUrls в bridge_wrapper.py

Bridge events (`extractBridgeEvent`) возвращают `mediaUrls` — массив путей к скачанным файлам. `bridge_wrapper.py` передаёт их как `_media` в message record:

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

### 3. Чтение из кеша в main_waha.py

Вместо запроса к Evolution API, бот читает локальный файл:

```python
media_meta = msg.get("_media")
if media_meta and media_meta.get("mediaType") == "document":
    local_path = media_meta.get("mediaUrls", [])[0]
    if local_path and os.path.exists(local_path):
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
```

### 4. Примечание о messageId

Мост возвращает `messageId` (не `timestamp`) как ID сообщения. `bridge_wrapper.py` должен использовать `m.get("messageId")` для ключа `key.id`, иначе бот не сможет отслеживать seen-сообщения и будет дублировать обработку.

## Проверка

```bash
# Кеш-директория существует
ls /tmp/hermes-media-cache/

# Мост запущен с кешем
pgrep -af bridge.js

# Здоровье моста
curl -s http://127.0.0.1:3000/health
```
