# Domain: agent-routing-safety

## Role
Безопасность маршрутизации: кто может слать в боевую группу, гейты авторизации. Production send — только по approval Сергея.

## Canonical Sources
- `AGENTS.md` (production send approval)
- `bot/authorized_senders.json`

## Code Owners
- `bot/authority.py`
- `bot/claim_gate.py`

## Neighbor Risks
- `whatsapp-bridge` (канал доставки)

## Known Traps
- Боевая группа `120363400682390076@g.us` — read-only, НЕ авто-отправка.
- Песочница `120363179621030401@g.us` — можно слать для тестов.

## GWT Scenarios

### GIVEN messaging.py для отправки `agent-routing-safety.messaging_imports_secrets_from_config`
- WHEN AST-анализ top-level imports `bot/messaging.py`
- THEN `EVO` и `KEY` импортируются из `config`, и НЕ импортируются из `bridge_wrapper`

### GIVEN fill_ejo.py и мёртвый Evolution API `agent-routing-safety.fill_ejo_no_evolution_imports`
- WHEN AST-анализ top-level imports `bot/fill_ejo.py`
- THEN НЕ импортирует `EVO`/`KEY` из `bridge_wrapper` (Evolution API мёртв — фото читаются с диска через pf.local_path)

### GIVEN production-deny контракта can_send `agent-routing-safety.can_send_fail_closed`
<!-- no-ci -->
**UNTESTED (CI):** authority.py не имеет исполняемых тестов (долг); при появлении теста — маркер сюда
- WHEN `can_send(chat_id, actor, approval_token)`
- THEN sandbox → True; production без approval_token → False; production с token → True; неизвестный chat_id → False (fail-closed ядро production-deny)

## Update Rule
Менялись гейты/роли → обнови контракты в `bot/test_contracts.py` (маркеры agent-routing-safety) + AGENTS.md.
