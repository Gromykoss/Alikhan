# 🏗️ Alikhan — the AI Construction Foreman on WhatsApp

> Turn everyday site messages into structured construction records, daily reports, and acceptance documents.
>
> Превращает сообщения со стройплощадки в структурированные журналы, ежедневные отчёты и исполнительные документы.

[![Version](https://img.shields.io/badge/version-v5.0_OJR-blue)](https://github.com/Gromykoss/Alikhan)
[![Python](https://img.shields.io/badge/python-3.11-green)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14_OJR_tables-blue)](db/ojr_schema.sql)
[![VOR](https://img.shields.io/badge/VOR-837_codes-orange)](report/templates/ВОР_с_расценками.xlsx)
[![AVR tests](https://img.shields.io/badge/AVR_tests-3%2F3-brightgreen)](bot/test_avr.py)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

Alikhan is a WhatsApp-native AI agent for construction operations at the Jeruy project. It captures field updates, uses Grok to extract facts, maintains a 14-table OJR database, generates EJO workbooks, and turns the EJO template into KS-2 and KS-6 acceptance records.

Alikhan — WhatsApp-native AI-агент для стройки на проекте Джеруй: собирает сообщения с площадки, извлекает факты через Grok, ведёт 14 таблиц ОЖР, формирует ЕЖО и выпускает КС-2/КС-6 из шаблона ЕЖО.

## Architecture in one line

```text
WhatsApp → Hermes Bridge :3000 → main_waha.py → Grok AI → PostgreSQL OJR → EJO → KS-2 + KS-6
```

## Key numbers / Ключевые цифры

| **837** | **14** | **780+** | **0** | **3/3** |
|:---:|:---:|:---:|:---:|:---:|
| VOR work codes | OJR tables | KS-6 rows | missing prices | AVR tests passing |
| кодов ВОР | таблиц ОЖР | строк КС-6 | пропущенных расценок | теста АВР проходят |

## Quick start / Быстрый старт

```bash
git clone https://github.com/Gromykoss/Alikhan.git
cd Alikhan
pip install -r requirements.txt

# Hermes WhatsApp Bridge must be available on :3000
curl -s http://127.0.0.1:3000/health

# Start the Python bot / Запустить Python-бота
./start_bot.sh

# Verify AVR generation / Проверить генерацию АВР
python3 -m pytest bot/test_avr.py -q
```

Runtime entry point: `bot/main_waha.py`, launched through `start_bot.sh`. The WhatsApp transport is Hermes Bridge—not Evolution API.

Точка входа: `bot/main_waha.py`, запуск через `start_bot.sh`. WhatsApp-транспорт — Hermes Bridge, не Evolution API.

## AVR: KS-2 + KS-6 / АВР: КС-2 + КС-6

`bot/avr.py` generates both acceptance-document formats from the canonical EJO workbook template at `bot/templates/ЕЖО_шаблон.xlsx`. AVR does **not** use `ojr_section3_work_log` as its document source.

`bot/avr.py` формирует оба документа из канонического Excel-шаблона `bot/templates/ЕЖО_шаблон.xlsx`. Источник АВР — **не** таблица `ojr_section3_work_log`.

- **KS-2 / КС-2** — acceptance act for the selected reporting period, with contract quantities, previous and current progress, totals, deductions, and signatures.
- **KS-6 / КС-6** — one cumulative four-section grouped table: all estimated work, completed since project start, completed during the reporting period, and remaining work.
- **Pricing / Расценки** — `report/templates/ВОР_с_расценками.xlsx`: 837 VOR codes, 780+ KS-6 rows, zero missing prices.
- **WhatsApp commands / Команды** — `АВР`, `формируй АВР`, `кс-2`, `кс-6`.
- **Verification / Проверка** — `python3 -m pytest bot/test_avr.py -q` → **3/3 passed**.

## Data flow / Поток данных

```text
FIELD OPERATIONS / ПЛОЩАДКА
WhatsApp messages + photos
Сообщения + фотографии
          │
          ▼
Hermes Bridge :3000 → bridge_wrapper.py → main_waha.py
          │
          ▼
Guard → Router → QA / Grok / Weather / Schedule / Poll
          │
          ├──► PostgreSQL: 14 OJR tables / 14 таблиц ОЖР
          │       ├── personnel / ИТР
          │       ├── work log / журнал работ
          │       ├── weather / погода
          │       └── photos, materials, incidents / фото, материалы, инциденты
          │
          └──► EJO Excel / ЕЖО Excel
                    └──► AVR / АВР: KS-2 + grouped KS-6
                                      КС-2 + группированная КС-6
```

## Project structure / Структура проекта

```text
Alikhan-migration/
├── bot/
│   ├── main_waha.py          # WhatsApp bot runtime / основной цикл бота
│   ├── bridge_wrapper.py     # Hermes Bridge adapter / адаптер моста
│   ├── router.py             # command and AI routing / маршрутизация
│   ├── qa.py                 # Grok fact extraction / извлечение фактов
│   ├── fill_ejo.py           # EJO generator / генератор ЕЖО
│   ├── avr.py                # KS-2 + KS-6 generator / генератор АВР
│   ├── test_avr.py           # 3 AVR tests / 3 теста АВР
│   ├── ojr_sync.py           # facts → OJR synchronization
│   └── templates/ЕЖО_шаблон.xlsx
├── db/
│   ├── ojr_schema.sql        # 14-table OJR schema / схема ОЖР
│   ├── ojr_er_diagram.md     # data model / модель данных
│   └── ojr_fill_guide.md     # operating guide / руководство
├── report/templates/
│   └── ВОР_с_расценками.xlsx # 837 priced VOR codes
├── start_bot.sh              # launches bot/main_waha.py
└── README.md
```

## Documentation / Документация

| Document | English / Русский |
|:---|:---|
| [Presentation pitch](PRESENTATION_PITCH.md) | Product story and Jeruy case / презентация и кейс Джеруй |
| [Technical requirements](TECHNICAL_REQUIREMENTS.md) | Infrastructure and deployment / инфраструктура и развёртывание |
| [Project index](INDEX.md) | Canonical files and workflows / карта файлов и процессов |
| [Operator runbook](RUNBOOK.md) | Operations and diagnostics / эксплуатация и диагностика |
| [OJR schema](db/ojr_schema.sql) | PostgreSQL source of truth / схема PostgreSQL |
| [OJR ER diagram](db/ojr_er_diagram.md) | Data relationships / связи данных |
| [OJR fill guide](db/ojr_fill_guide.md) | OJR population workflow / заполнение ОЖР |
| [Chronology](CHRONOLOGY.md) | Project history / история проекта |
| [Agent rules](AGENTS.md) | Safety and development rules / правила разработки |

---

**Alikhan v5 — construction intelligence where the work already happens: WhatsApp.**

**Alikhan v5 — строительный интеллект там, где уже идёт работа: в WhatsApp.**
