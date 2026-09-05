# Domain: whatsapp-bridge

## Role
Приём/отправка сообщений WhatsApp через Hermes Bridge (Baileys, `:3000`, mode=bot). Мост живёт ВНУТРИ gateway — отдельного systemd-юнита `hermes-whatsapp-bridge` НЕ существует.

## Canonical Sources
- `bot/CONTRACTS.md` §2.11 (whatsapp_commands — точка входа)
- `AGENTS.md` (конфиг bridge)
- `PROJECT_MEMORY_GRAPH.md` (инвариант: рестарт gateway запрещён)

## Code Owners
- `bot/whatsapp_commands.py` (диспетчер: poll боевой группы, ACK)
- `bot/messaging.py`

## Neighbor Risks
- `data-ingestion` (диспетчер пишет сырьё ДО ack)
- `agent-routing-safety` (production send — approval)

## Known Traps
- `curl :3000/health` → `status:connected` НЕ значит, что inbound расшифровывается (decrypt-ошибки «No session found»).
- Активный journal: `~/.hermes/profiles/alikhan/whatsapp/session/collect_journal.jsonl` (НЕ legacy `whatsapp/collect_journal.jsonl`).

## Update Rule
Менялись endpoints / поведение моста → обнови CONTRACTS.md §bridge + эту карточку.
