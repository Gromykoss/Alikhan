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

## Update Rule
Менялись гейты/роли → обнови `test_smoke.py` (authority) + AGENTS.md.
