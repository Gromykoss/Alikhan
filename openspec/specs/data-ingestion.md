# Domain: data-ingestion

## Role
Сырьё-слой: `bot_memory_messages` — ЖИВОЙ поток (песочница + боевая). Диспетчер пишет каждое сообщение/фото/документ ДО ack. Если строка есть здесь — факт прихода НЕ потерян.

## Canonical Sources
- `DATA_CONTRACT.md` (источник сырья + правило разрыва)

## Code Owners
- `bot/db_memory.py`
- `bot/whatsapp_commands.py` (`_save_prod_text` / `_save_prod_photo` / `_save_prod_document`)

## Neighbor Risks
- `ojr-data-contract` (разбор сырья → ojr_*)
- `qa-parser` (текст → факты)

## Known Traps
- «Сырьё растёт, ojr_* не растёт = разрыв РАЗБОРА, не потеря данных». Чинить разбор (код), НЕ «восстанавливать данные».

## Update Rule
Менялся маршрут записи сырья → обнови DATA_CONTRACT.md + эту карточку.
