# Alikhan Bot v3 — полное восстановление всех функций n8n

## Guard (уже есть ✅)
- allowedGroups: sandbox + production
- Фильтр "алихан" (case-insensitive)
- fromMe=false
- Текстовые, фото, документы

## Router — 15 команд (порядок приоритета важен!)

1. `only_name` — текст === "алихан"
2. `memory_status` — "статус памяти"
3. `calendar_delete` — ID + "удали/отмени событие"
4. `document_compare` — 2+ ID + "сравни документ"
5. `current_datetime` — "какой сегодня день", "сколько времени"
6. `fact_lookup` — regulation fact ("можно ли", "по регламенту") ИЛИ "подними/найди/покажи/расскажи подробнее"
7. `id_lookup` — ID + "покажи/найди/подними"
8. `calendar_create` — "добавь событие", "создай событие", "запланируй"
9. `calendar_list` — "календарь", "события", "что сегодня/завтра/на неделю". calendarRange: today/tomorrow/week/all
10. `participant_activity` — "кто чаще всего писал"
11. `group_participants` — "участники", "кто в группе"
12. `period_summary` — "сводка/самари/итоги" + парсинг дат (вчера/сегодня/месяц/диапазон с-по)
13. `quoted_document_summary` — quoted message + документ
14. `who_are_you` — "кто ты"
15. `ai` — DEFAULT

## Handlers

### Calendar (cale) — 3 подкоманды:
- `calendar_list` — SELECT bot_calendar_events WHERE chat_id='...' AND (today/tomorrow/week/all)
- `calendar_create` — xAI extraction → INSERT
- `calendar_delete` — DELETE WHERE id=lookupId

### Fact lookup (fact)
- Искать в bot_memory_messages по ILIKE
- Отправить в xAI для суммаризации
- Цитировать ID сообщений

### ID lookup (id_l)
- SELECT * FROM bot_memory_messages WHERE id=lookupId
- Показать содержимое

### Period summary (peri)
- SELECT сообщения за диапазон дат from bot_memory_messages
- xAI суммаризация
- Вывод: кто что писал, ключевые темы

### Current datetime (curr)
- Просто вернуть текущие дату/время

### Who are you (who_)
- "Я Алихан — AI-ассистент..."

### Document compare (docu)
- 2 документа по ID
- Сравнить через xAI

### Quoted document summary (quot)
- Ответ на цитируемый документ

### Group participants (grou)
- SELECT from bot_group_participants

### Participant activity (part)
- Анализ активности участников

### Only name (only)
- Приветственное сообщение

### Memory status (memo)
- Статистика памяти

## Photo handling
- Guard Photo срабатывает на imageMessage
- Скачать через getBase64FromMediaMessage
- Отправить в xAI Vision (https://api.x.ai/v1/chat/completions с vision)
- Ответить с анализом фото

## Document handling
- Guard Document срабатывает на documentMessage
- Скачать через getBase64FromMediaMessage
- Извлечь текст (? через внешний сервис или xAI)
- Сохранить в bot_memory_messages
- Ответить с кратким содержанием

## PostgreSQL schema
- bot_calendar_events: id, chat_id, title, description, event_start, event_end, status
- bot_memory_messages: id, chat_id, sender, message_time, role, message_type, content, summary
- bot_memory_summaries: id, chat_id, summary, messages_until_id
- bot_group_participants: нужно проверить схему

## Redis (опционально)
- Кэш контекста диалога

## API endpoints
- Evolution: sendText, getBase64FromMediaMessage, findMessages
- xAI: chat/completions (текст + vision + extraction)
