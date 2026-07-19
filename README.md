# <img src="https://img.icons8.com/fluency/48/000000/construction.png" width="32"> Alikhan — Автономный AI-прораб на WhatsApp

> **Стройка, которая отчитывается сама.**

[![Version](https://img.shields.io/badge/version-v5.0_OЖР-blue)](https://github.com/Gromykoss/Alikhan)
[![Python](https://img.shields.io/badge/python-3.11-green)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14_tables-blue)](db/ojr_schema.sql)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**Alikhan** — AI-агент для управления строительством через WhatsApp. Собирает данные от прорабов, парсит через Grok (xAI), заполняет 14 таблиц ОЖР по ГОСТ РД-11-05-2007, формирует ЕЖО за 30 секунд. **Сам чинит и улучшает свой код.**

---

## Архитектура одной строкой

```
WhatsApp → Hermes Bridge (:3000) → Python-бот (main_waha.py) → Grok AI → PostgreSQL (14 таблиц ОЖР) → ЕЖО (Excel)
```

---

## Ключевые цифры

| | | | |
|:---:|:---:|:---:|:---:|
| **14** | **69** | **2 765** | **71** |
| таблиц ГОСТ ОЖР | записей работ с VOR-кодами | фото с AI-описанием (Grok Vision) | ИТР-сотрудников в базе |
| **18** | **827** | **1 день** | **443 млн ₽** |
| дней сводок (daily summary) | дней графика СМР (8 этапов) | на клонирование под объект | контракт ЕРС |

---

## 🚀 Быстрое начало

```bash
# Проверка статуса
curl -s http://127.0.0.1:3000/health                     # Hermes Bridge
systemctl --user status hermes-whatsapp-bridge            # WhatsApp Bridge
systemctl status alikhan-bot                              # Python-бот
tail -30 /tmp/alikhan.log                                 # Логи

# Health check (8 измерений)
python3 ~/.hermes/scripts/alikhan_health_check.py

# Перезапуск бота
sudo systemctl restart alikhan-bot

# Бэкап БД
python3 /home/hermes-workspace/Alikhan-migration/bot/backup_db.py
```

---

## 📚 Документация

| Документ | Описание |
|:---------|:---------|
| [📄 **PRESENTATION_PITCH.md**](PRESENTATION_PITCH.md) | Презентация для клиентов — проблема, решение, кейс ТЗРК Джеруй |
| [⚙️ **TECHNICAL_REQUIREMENTS.md**](TECHNICAL_REQUIREMENTS.md) | Технические условия — VPS, API-ключи, варианты развёртывания |
| [📡 **COMMUNICATION_CHANNELS.md**](COMMUNICATION_CHANNELS.md) | Каналы связи — WhatsApp, Telegram, Discord |
| [🧠 **SKILL_METHODOLOGY.md**](SKILL_METHODOLOGY.md) | Методика создания AI-навыков Hermes Agent |
| [🤖 **JUNIOR_HERMES_PLAN.md**](JUNIOR_HERMES_PLAN.md) | План архитектуры автономного Junior Hermes «Alikhan» |

**Дополнительно:**
- [📋 **AGENTS.md**](AGENTS.md) — правила для Hermes-агента
- [📑 **INDEX.md**](INDEX.md) — навигация по проекту
- [🔧 **RUNBOOK.md**](RUNBOOK.md) — руководство оператора
- [💰 **PRICING_SLA.md**](PRICING_SLA.md) — тарифы и SLA
- [📅 **CHRONOLOGY.md**](CHRONOLOGY.md) — история изменений

---

## 🧱 Структура проекта

```
Alikhan-migration/
├── bot/                     # Python-бот (v5, OJR)
│   ├── main_waha.py         # Главный цикл — poll 3s, Guard, command handlers
│   ├── router.py            # Маршрутизация: QA, Grok, DB, Schedule, Poll
│   ├── fill_ejo.py          # Генератор ЕЖО — view на ojr_section3_work_log
│   ├── qa.py                # QA-парсер — извлечение фактов через Grok
│   ├── poll.py              # Ежедневный опрос прорабов
│   ├── db.py                # PostgreSQL — сообщения, факты, календарь
│   ├── bridge_wrapper.py    # Monkey-patch Evolution API → Hermes Bridge
│   ├── ojr_sync.py          # Синхронизация bot_memory_facts → таблицы ОЖР
│   ├── document_extractor.py # Документ-экстрактор (:8099)
│   ├── backup_db.py         # Бэкап/восстановление PostgreSQL
│   ├── alerter.py           # Telegram-алерты
│   ├── metrics.py           # Prometheus-метрики
│   ├── config.py            # Централизованный конфиг
│   ├── graceful.py          # Graceful degradation (fallback, retry)
│   ├── validate_ejo.py      # Валидация ЕЖО перед отправкой
│   └── watchdog_bridge.py   # Watchdog для Hermes Bridge
├── db/
│   ├── ojr_schema.sql       # Схема БД — 14 таблиц ОЖР (ГОСТ РД-11-05-2007)
│   ├── ojr_er_diagram.md    # ER-диаграмма
│   └── ojr_fill_guide.md    # Руководство по заполнению
├── skills/                  # Hermes Agent навыки (9 шт.)
├── n8n-workflows/           # Исторические n8n workflow (архив)
├── PRESENTATION_PITCH.md    # Презентация
├── TECHNICAL_REQUIREMENTS.md # Технические условия
├── COMMUNICATION_CHANNELS.md # Каналы связи
├── SKILL_METHODOLOGY.md     # Методика навыков
├── JUNIOR_HERMES_PLAN.md    # План Junior Hermes
├── PRICING_SLA.md           # Тарифы и SLA
├── RUNBOOK.md               # Руководство оператора
└── README.md                # ← вы здесь
```

---

## 🔄 Поток данных (v5 — ОЖР)

```
WhatsApp → Hermes Bridge :3000 → bridge_wrapper.py → main_waha.py (poll 3s)
  → Guard → Router → [QA/DB/Weather/Grok/Schedule/Poll] → Reply
                          │
                          ▼ QA-парсер (qa.py)
                    bot_memory_facts (промежуточный слой)
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
   ┌──────────────┐ ┌────────────┐ ┌──────────┐
   │ojr_section1  │ │ojr_section3│ │  ojr_    │
   │_personnel    │ │_work_log   │ │ weather  │
   └──────────────┘ └─────┬──────┘ └──────────┘
            │             │             │
            │    ┌────────┼────────┐    │
            │    ▼        ▼        ▼    │
            │ ┌──────┐┌──────┐┌──────┐ │
            │ │photo ││daily ││mater-│ │
            │ │_log  ││_summ ││ials  │ │
            │ └──────┘└──┬───┘└──────┘ │
            │            │             │
            └────────────┼─────────────┘
                         ▼
                  ЕЖО (fill_ejo.py)
```

---

## ⚡ Quick Links

| Ресурс | Команда / URL |
|:-------|:--------------|
| 🏥 Health check | `python3 ~/.hermes/scripts/alikhan_health_check.py` |
| 🌉 Bridge health | `curl -s http://127.0.0.1:3000/health` |
| 📊 Prometheus | `http://localhost:9090/metrics` |
| 📝 Логи | `tail -f /tmp/alikhan.log` |
| 💾 Бэкапы | `/backups/` (30-дневная ротация) |
| 🧪 Песочница | WhatsApp (тестовая группа) |
| 🏭 Production | WhatsApp (боевая группа) |

---

*Alikhan v5.0 — ОЖР · ТЗРК Джеруй · 18 июля 2026*
