# PROJECT_MEMORY_GRAPH.md — единый вход сессии Alikhan

> Назначение: компактная карта проекта, читается на старте ВМЕСТО больших доков.
> Обновляется: при изменении доменов / инвариантов / тестов (Spec Drift Gate, внизу).

## Purpose
WhatsApp-агент Alikhan для стройплощадки ТЗРК Джеруй: приём фактов от прорабов → разбор (QA) → хранение (ОЖР) → отчёты (ЕЖО/АВР). Прямой Hermes Bridge (Baileys), без отдельного Python-бота.

## Boot Rule
1. Читай ТОЛЬКО этот файл на старте. Большие доки (MASTER_SPEC, DATA_CONTRACT, CONTRACTS) — НЕ читай сразу: открывай по маршруту (Change Routing).
2. Задача про домен → открой карточку домена в `openspec/specs/`, затем указанный в ней источник.
3. Anti-context-bloat: deep sources (CHRONOLOGY, MASTER_SPEC, CONTRACTS) — только через карточку, никогда целиком на старте.

## Global Invariants (нарушение = стоп + эскалация)
- **Канон ОЖР = 15 таблиц** (не 14). В БД 17 = 15 + `ojr_pass_register` + `ojr_vor_reference`.
- **Сырьё растёт, `ojr_*` не растёт = РАЗРЫВ РАЗБОРА, НЕ потеря данных.** Данные целы в `bot_memory_messages`.
- **Production send (`120363400682390076@g.us`) — только по approval Сергея.**
- **Рестарт gateway запрещён** (общий ресурс) — только Сергей/оператор. Мост живёт в gateway, unit `hermes-whatsapp-bridge` НЕ существует.
- **Timezone = Бишкек UTC+6.** Все даты — Бишкек.
- **Код не пишу сам** — Codex (Maker) / Grok (Checker) по DELEGATION GATE.

## Domain Map

| Домен | Карточка | Источники | Код | Тесты | Соседи риска |
|-------|----------|-----------|-----|-------|--------------|
| whatsapp-bridge | `openspec/specs/whatsapp-bridge.md` | `bot/CONTRACTS.md` §2.11, `AGENTS.md` | `bot/whatsapp_commands.py` | `bot/test_contracts.py`, `bot/test_smoke.py`, `bot/tests/test_bridge_contract.py` | data-ingestion, agent-routing-safety |
| data-ingestion | `openspec/specs/data-ingestion.md` | `DATA_CONTRACT.md` | `bot/db_memory.py`, `bot/whatsapp_commands.py` | `bot/test_smoke.py` | ojr-data-contract, qa-parser |
| ojr-data-contract | `openspec/specs/ojr-data-contract.md` | **`DATA_CONTRACT.md`** (узел), `bot/CONTRACTS.md` §2.2 | `bot/db.py`, `db/ojr_schema.sql`, `bot/data_sources.py` | `bot/test_contracts.py`, `bot/tests/test_namedtuple_schemas.py` | data-ingestion, ejo-generation, qa-parser |
| ejo-generation | `openspec/specs/ejo-generation.md` | `MASTER_SPEC.md` §6, `bot/CONTRACTS.md` §2.9 | `bot/fill_ejo.py`, `bot/ejo_backfill.py`, `bot/update_template.py` | `bot/ejo_simulation_check.py` (script), `bot/tests/test_ejo_template_contract.py` | ojr-data-contract |
| avr-generation | `openspec/specs/avr-generation.md` | `MASTER_SPEC.md` §6 | `bot/avr.py` + `report/templates/ВОР_с_расценками.xlsx` | `bot/test_avr.py` | ejo-generation, vor-import |
| qa-parser | `openspec/specs/qa-parser.md` | `bot/CONTRACTS.md` §2.5 | `bot/qa.py` | `bot/test_qa_parser.py`, `bot/tests/test_grok_qa_schema.py`, `bot/tests/test_qa_golden.py` | data-ingestion, ojr-data-contract |
| agent-routing-safety | `openspec/specs/agent-routing-safety.md` | `AGENTS.md` | `bot/authority.py`, `bot/claim_gate.py` | `bot/test_smoke.py` | whatsapp-bridge |
| document-extraction | `openspec/specs/document-extraction.md` | `INDEX.md`, `bot/document_extractor.py` | `bot/document_extractor.py` + `:8099` | — | data-ingestion, ojr-data-contract |
| vor-import (пилот) | `openspec/specs/vor-import.md` | `bot/CONTRACTS.md` §2.9b | `bot/vor_reference.py` | `bot/test_vor_reference.py` | avr-generation |

## Change Routing (задача про X → читать Y)
- **ЕЖО** → `openspec/specs/ejo-generation.md` + `bot/fill_ejo.py` + `bot/tests/test_ejo_template_contract.py`
- **АВР / КС-2 / КС-6** → `openspec/specs/avr-generation.md` + `bot/avr.py` + `bot/test_avr.py` + `report/templates/ВОР_с_расценками.xlsx`
- **ВОР-коды / справочник** → `openspec/specs/vor-import.md` + `bot/vor_reference.py`
- **production send** → `openspec/specs/agent-routing-safety.md` + `openspec/specs/whatsapp-bridge.md`
- **данные / таблицы ОЖР** → `openspec/specs/ojr-data-contract.md` + `DATA_CONTRACT.md`
- **фото/документы** → `openspec/specs/document-extraction.md` + `openspec/specs/data-ingestion.md`
- **приём сообщений** → `openspec/specs/whatsapp-bridge.md` + `openspec/specs/data-ingestion.md`
- **QA-разбор фактов** → `openspec/specs/qa-parser.md` + `bot/qa.py`

## Spec Drift Gate
После изменения домена / инварианта / теста — обнови этот граф И соответствующую карточку. Если изменение НЕ затрагивает контракты — запиши в CHRONOLOGY одну строку: `Contract index update: not needed`.
