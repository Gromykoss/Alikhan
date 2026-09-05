# Навыки Alikhan — индекс

> Проект: WhatsApp AI-агент для ТЗРК Джеруй
>
> Всего навыков: **11** (9 готовых, 2 запланированы)
>
> Дата сборки: 2026-07-18

---

## Категория `alikhan` — логика бота и ЕЖО

### 1. alikhan-fill-ejo
> **Полная логика заполнения и формирования ЕЖО** — все колонки, скрытие строк, персонал, планы, отправка.

| Параметр | Значение |
|----------|----------|
| Строк | 77 |
| References | 1 |
| Ключевые темы | Колонки L–U, скрытие строк, табель, материалы, отправка, vision-описание фото |
| Зависит от | alikhan-operations, alikhan-poll-logic |
| Путь | `alikhan/alikhan-fill-ejo/SKILL.md` |

---

### 2. alikhan-operations
> **Operational patterns** — DB migrations, schedule management, data extraction, project conventions, QA parser architecture.

| Параметр | Значение |
|----------|----------|
| Строк | 544 |
| References | 22 |
| Ключевые темы | WORKFLOW DISCIPLINE, SANDWICH RULE, DB operations (14 OJR tables), ЕЖО workflow v3, QA parser 2-stage extraction, calendar reminders, verification tools |
| Зависит от | — (корневой навык) |
| Путь | `alikhan/alikhan-operations/SKILL.md` |

> ⚠️ **Самый объёмный навык.** 50+ pitfalls, полная документация всех модулей бота.

---

### 3. alikhan-poll-logic
> **Логика ежемесячного плана и ежедневного опроса** — фильтр O>0 ∧ U>0, команды, pitfalls.

| Параметр | Значение |
|----------|----------|
| Строк | 97 |
| References | 1 |
| Ключевые темы | Месячный цикл (раскрой → план → опрос), фильтр опроса, 3 этапа — не мешать, HTTP 413 fix, sendMedia через bridge_wrapper |
| Зависит от | alikhan-fill-ejo |
| Путь | `alikhan/alikhan-poll-logic/SKILL.md` |

---

### 4. alikhan-daily-snapshot 🔵
> **Ежедневный снимок дня** — собирает фото, сообщения, документы, QA, ЕЖО и погоду. Нарратив через Ollama, xAI только для vision.

| Параметр | Значение |
|----------|----------|
| Строк | 140 |
| References | 3 |
| Ключевые темы | Разделение движков (xAI vs Ollama), timezone pitfall (Бишкек UTC+6), структурированный промпт v2, 10+ pitfalls |
| Зависит от | alikhan-photo-vision, alikhan-poll-logic |
| Путь | `alikhan-daily-snapshot/SKILL.md` |

---

### 5. alikhan-photo-vision 🔵
> **Автоматическое описание фото** через Grok vision API. Сохранение в БД с тегом здания и текстовым описанием.

| Параметр | Значение |
|----------|----------|
| Строк | 65 |
| References | 1 |
| Ключевые темы | Bridge → wrapper → bot media flow, escalation (speculative words), промпт для Grok, правило движков |
| Зависит от | alikhan-daily-snapshot |
| Путь | `alikhan-photo-vision/SKILL.md` |

---

### ~~6. alikhan-monthly-template~~ ⚠️ Запланирован
> Подготовка шаблона следующего периода — «Алихан раскрой отчет».

**Статус:** SKILL.md отсутствует на диске. Навык зарегистрирован в системе (`available_skills`) но файл не создан.  
**Зависит от:** alikhan-poll-logic

---

### ~~7. alikhan-template-handoff~~ ⚠️ Запланирован
> Суточный цикл передачи шаблона ЕЖО — от генерации до следующего утра.

**Статус:** SKILL.md отсутствует на диске. Навык зарегистрирован в системе но файл не создан.  
**Зависит от:** alikhan-fill-ejo, alikhan-poll-logic

---

## Категория `project` — проектная документация

### 8. alikhan-ejo-report
> **Проект Алихан — ЕЖО АйБиКон** — автоматическое формирование Excel-отчётов через openpyxl, smart evening check, cumulative volume chaining, photo embedding.

| Параметр | Значение |
|----------|----------|
| Строк | 996 |
| References | 16 |
| Версия | 2.21.0 |
| Ключевые темы | Формат v3 (фото внутри листа 1), жёлтая заливка, готовность K853, cumulative chaining, manual template restore, Cyrillic filename workaround |
| Зависит от | alikhan-fill-ejo, ejo-daily-report |
| Путь | `project/alikhan-ejo-report/SKILL.md` |

> ⚠️ **Самый длинный навык.** 996 строк, 16 references, хронология изменений с 2026-06-29.

---

### 9. alikhan-whatsapp-bot
> **Build, debug, and deploy the Alikhan WhatsApp AI bot** — Python bot architecture, WhatsApp connection methods, n8n-to-Python migration, credential workarounds, STT/TTS, polling pagination.

| Параметр | Значение |
|----------|----------|
| Строк | 769 |
| References | 8 |
| Ключевые темы | Architecture (WhatsApp → Bridge → wrapper → bot), voice pipeline, QA parser (VOR code extraction), LLM routing (Ollama-first), poll system, Evolution API pagination, Russian word-stem matching |
| Зависит от | alikhan-maintenance |
| Путь | `project/alikhan-whatsapp-bot/SKILL.md` |

---

### 10. ejo-daily-report
> **ЕЖО ТЗРК Джеруй — методология заполнения** — опрос, проверка, fill_ejo, верификация.

| Параметр | Значение |
|----------|----------|
| Строк | 254 |
| References | 1 |
| Версия | 3.1.0 |
| Ключевые темы | Pipeline v3 (MONTHLY → POLL → FOREMAN → CLOSE → VERIFY), SIM_DATE workflow, QA-парсер, fill_ejo.py, 20+ pitfalls |
| Зависит от | alikhan-ejo-report |
| Путь | `project/ejo-daily-report/SKILL.md` |

---

## Категория `projects` — обслуживание и эксплуатация

### 11. alikhan-maintenance
> **Maintain and debug the Alikhan WhatsApp bot** — architecture, ЕЖО pipeline, common failure patterns, health checks, SIM_DATE workflow.

| Параметр | Значение |
|----------|----------|
| Строк | 440 |
| References | 9 |
| Scripts | 1 (health_check.py) |
| Ключевые темы | Golden Rule (Verify Before Reporting), 13 failure patterns, duplicate EJO prevention (triple guard + TOCTOU), production group listener, bridge crash fix, message deletion |
| Зависит от | — (корневой навык обслуживания) |
| Путь | `projects/alikhan-maintenance/SKILL.md` |

---

## Карта зависимостей

```
alikhan-maintenance ─────────────────────────────────────────┐
alikhan-whatsapp-bot ────────────────────────────────────────┤
alikhan-operations (корневой)                                │
  ├── alikhan-fill-ejo ──────────────────────────────────────┤
  │     ├── alikhan-poll-logic ──────────────────────────────┤
  │     │     ├── alikhan-monthly-template ⚠️ (запланирован)  │
  │     │     └── alikhan-template-handoff ⚠️ (запланирован)  │
  │     └── alikhan-daily-snapshot                           │
  │           └── alikhan-photo-vision                       │
  └── project/                                               │
        ├── alikhan-ejo-report                               │
        │     └── ejo-daily-report                           │
        └── alikhan-whatsapp-bot                             │
```

---

## Статистика

| Метрика | Значение |
|---------|----------|
| Всего навыков | 11 |
| Готовых (SKILL.md на диске) | 9 |
| Запланированных (без файла) | 2 |
| Суммарно строк SKILL.md | 3,382 |
| Суммарно references | 62 |
| Суммарно scripts | 1 |
| Средний объём навыка | 376 строк |
| Медианный объём | 254 строки |
| Самый большой | alikhan-ejo-report (996 строк) |
| Самый маленький | alikhan-photo-vision (65 строк) |

---

## Как использовать

### Загрузить навык
```python
skill_view('alikhan-fill-ejo')
skill_view('alikhan-operations')
```

### Загрузить reference внутри навыка
```python
skill_view('alikhan-operations', file_path='references/ojr-schema.md')
skill_view('alikhan-ejo-report', file_path='references/ejo-column-methodology.md')
```

### Создать новый навык
См. [`SKILL_METHODOLOGY.md`](../SKILL_METHODOLOGY.md) — полная методика создания навыков.

---

## Обозначения

- 🔵 — навык с автономным триггером (не требует команды пользователя)
- ⚠️ — навык запланирован, но SKILL.md отсутствует
- 🐉 — навык содержит pitfalls уровня P0 (критические)
