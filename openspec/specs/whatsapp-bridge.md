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

## GWT Scenarios

### GIVEN OpenAPI-контракт моста `whatsapp-bridge.openapi_contract_valid`
- WHEN чтение `docs/bridge_openapi.json`
- THEN json содержит непустые `paths` и `components`

### GIVEN живой bridge :3000 `whatsapp-bridge.health_matches_openapi`
<!-- no-ci -->
**UNTESTED (CI):** тест ходит в live bridge :3000 (VPS-only), в runner моста нет; прогон на VPS при деплое bridge
- WHEN GET /health
- THEN HTTP 200, поля status/queueLength/uptime/scriptHash/sendReadReceipts присутствуют, status == connected

### GIVEN живой bridge :3000 `whatsapp-bridge.ack_endpoint`
<!-- no-ci -->
**UNTESTED (CI):** live bridge :3000 (VPS-only)
- WHEN POST /messages-ack с пустым messageIds
- THEN HTTP != 404 (endpoint жив, контракт A+ соответствует; пустой список — валидный вызов)

### GIVEN живой bridge :3000 `whatsapp-bridge.collect_messages_dead`
<!-- no-ci -->
**UNTESTED (CI):** live bridge :3000 (VPS-only)
- WHEN GET /collect-messages
- THEN HTTP 404 (dead-контракт: endpoint удалён и не должен оживать)

## Update Rule
Менялись endpoints / поведение моста → обнови CONTRACTS.md §bridge + эту карточку.
