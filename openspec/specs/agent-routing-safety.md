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
- WHEN `can_send(chat_id, actor, approval_token)`
- THEN sandbox → True; production без approval_token → False; production с token → True; неизвестный chat_id → False

### GIVEN матрица прямых мутаций `agent-routing-safety.is_mutation_allowed_matrix`
- WHEN `is_mutation_allowed(level, actor_is_orchestrator)` получает каждый `AuthorityLevel`
- THEN orchestrator допускает только READ/ANALYZE; оператор допускает READ/ANALYZE/LOCAL и блокирует уровни выше

### GIVEN канонический argv buzz-send `agent-routing-safety.buzz_send_argv_canon`
- WHEN `_buzz_send_allowed(command)` разбирает terminal command через `shlex.split`
- THEN абсолютный `/usr/bin/python3` + канонический `buzz-send.py --as alikhan --to <target> <msg>` разрешён; `--as=alikhan`, shell-meta, короткий argv и невалидный shlex запрещены

### GIVEN файловая граница tool call `agent-routing-safety.guard_tool_call_file_boundary`
- WHEN `guard_tool_call(tool_name, args)` рекурсивно собирает `path` из dict/list payload
- THEN path внутри `~/Alikhan-migration` разрешён; path вне зоны запрещён; вложенные path проверяются рекурсивно; unknown tool не блокируется

### GIVEN terminal-фрагменты вне зоны `agent-routing-safety.guard_terminal_fragments`
- WHEN `guard_tool_call("terminal", {"command": command})` проверяет shell-команду
- THEN команды с запрещёнными фрагментами блокируются; пустая command блокируется; канонический buzz-send разрешён; неканонический `buzz-send.py` блокируется; обычный `ls bot/` разрешён

## Update Rule
Менялись гейты/роли → обнови `bot/test_contracts.py` и `bot/test_authority.py` (маркеры agent-routing-safety) + AGENTS.md.
