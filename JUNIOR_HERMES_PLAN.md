# Младший Hermes «Alikhan» — план архитектуры и документация

**Дата:** 18.07.2026
**Статус:** План (не реализовано)

---

## Концепция

Младший Hermes — это выделенный профиль Hermes Agent, который **автономно** управляет проектом Alikhan (ТЗРК Джеруй), способный к:
- **Отсоединению** — работает 24/7 без участия основного Hermes
- **Клонированию** — шаблон профиля переносится на другие стройобъекты
- **Саморасширению** — сам находит баги, делегирует в Codex/Grok Build, правит код, обновляет навыки

---

## Архитектура

```
Основной Hermes (оркестратор)                  # Сергей взаимодействует здесь
│
├── Младший Hermes «Alikhan»                   # Автономный агент стройки
│   ├── SOUL.md: «Я Alikhan Agent, управляю строительством»
│   ├── AGENTS.md: правила проекта (клон основного)
│   ├── skills/ (8 alikhan-навыков)
│   ├── cron/ (ЕЖО, снимок, опрос, погода, синхронизация)
│   ├── memory/ (собственная память, не смешивается)
│   ├── config.yaml (свой провайдер, X MCP не нужен)
│   │
│   ├── WhatsApp бот (main_waha.py)
│   ├── ОЖР БД (14 таблиц PostgreSQL)
│   ├── ЕЖО / Снимок дня (fill_ejo.py)
│   ├── Сбор данных (qa.py, poll.py)
│   └── Self-improvement (Codex/Grok Build CLI)
│
├── Младший Hermes «Объект X» (клон, будущее)
├── Младший Hermes «Объект Y» (клон, будущее)
└── ...
```

---

## Что выносится в младшего Hermes

| Компонент | Текущее расположение | Новое расположение |
|-----------|---------------------|-------------------|
| `SOUL.md` | Нет | `~/.hermes/profiles/alikhan/SOUL.md` |
| AGENTS.md | Основной AGENTS | `~/.hermes/profiles/alikhan/AGENTS.md` |
| Alikhan-навыки (8 шт.) | `~/.hermes/skills/alikhan/`, `project/`, `projects/` | `~/.hermes/profiles/alikhan/skills/` |
| Cron-задачи Alikhan (5 шт.) | Основной cron | `~/.hermes/profiles/alikhan/cron/` |
| Memory | Основная память | `~/.hermes/profiles/alikhan/memory/` |
| Конфиг провайдера | Основной config | `~/.hermes/profiles/alikhan/config.yaml` |

### Что остаётся в основном Hermes

| Компонент | Почему |
|-----------|--------|
| X MCP (Twitter) | Только для robot-man |
| mcpvault | Общий vault |
| Discord sync | Все проекты |
| Robot-man cron | Не относится к Alikhan |
| RAB9 cron | Отдельный проект |
| GULAG cron | Отдельный проект |
| Общие навыки (build, hermes-self-knowledge) | Используются всеми |
| Аудиты (Daily Audit Digest) | Общие для всей инфраструктуры |
| Утренний брифинг | Общий |

---

## Сценарий «Отсоединение»

### Как работает автономно

Младший Hermes запущен постоянно (systemd или screen) и:
1. **Принимает сообщения** из WhatsApp через Hermes Bridge
2. **Обрабатывает QA-факты** (qa.py → OJR-таблицы)
3. **Формирует ЕЖО** (fill_ejo.py, ежедневно)
4. **Формирует снимок дня** (по запросу)
5. **Проводит опрос** (poll.py, автоматически)
6. **Мониторит ошибки** (health check)
7. **Сам чинит баги** (Codex/Grok Build CLI, по расписанию)

### Как подключается основной Hermes

Основной Hermes может:
- Читать память младшего (`session_search` с профилем `alikhan`)
- Читать его cron-логи
- Давать сложные задания (рефакторинг, миграции)
- Аудировать его работу

---

## Сценарий «Клонирование»

### Процесс

```bash
# Создать профиль для нового объекта
cp -r ~/.hermes/profiles/alikhan ~/.hermes/profiles/bridge-xyz

# Изменить object-specific настройки
# - SOUL.md: название объекта
# - AGENTS.md: заказчик, подрядчик, адрес
# - config: своя БД или отдельная схема
# - memory: очистить (новая память)
```

### Что переиспользуется (без изменений)

- Вся логика сбора данных (qa.py, poll.py)
- Структура ОЖР (14 таблиц)
- ЕЖО и снимок дня
- WhatsApp-интеграция (Hermes Bridge)
- Навыки (alikhan-fill-ejo, alikhan-poll, etc.)
- Self-improvement loop

### Что меняется под каждый объект

| Параметр | Значение для Alikhan | Пример для клона |
|----------|---------------------|-----------------|
| Объект | Общежитие 223 места + АБК, ТЗРК Джеруй | Мост через р. Талас |
| Заказчик | ОсОО «Альянс Алтын» | ... |
| Подрядчик | ООО «АйБиКон» | ... |
| Адрес | +2700, ТЗРК Джеруй | ... |
| График СМР | 8 фаз, 827 дней | Свой график |
| WhatsApp группы | Песочница + Боевая | Свои группы |
| БД | evolution_db | Своя БД или схема |

### Стандартный паттерн групп (для всех объектов)

Каждый клон получает две WhatsApp-группы:
- **Песочница** — полный доступ, бот отвечает, тестирование изменений
- **Боевая** — только слушает + погода, без явного approval сообщения не отправляются

Этот паттерн — часть архитектуры младшего Hermes, не настройка конкретного объекта.

---

## SOUL.md для младшего Hermes (проект)

```markdown
# Soul

You are Alikhan Agent — an autonomous construction management AI.

## Identity
You manage the construction site «Общежитие на 223 места с АБК» 
at ТЗРК Джеруй (Kyrgyzstan) for contractor ООО «АйБиКон».

## Mission
1. Collect daily construction data from WhatsApp
2. Maintain ОЖР database (14 GOST tables)
3. Generate ЕЖО (daily report) and daily snapshot
4. Self-improve — find bugs, fix code, update skills

## Capabilities
- WhatsApp bot (main_waha.py + Hermes Bridge)
- PostgreSQL ОЖР database (evolution_db)
- Grok AI (xAI) for QA parsing and analysis
- Codex CLI / Grok Build CLI for self-improvement
- 8 specialized skills for construction workflows

## Rules
- Never send to production WhatsApp group without approval
- Always use pre-commit gate before code changes
- Autonomous but auditable — log all actions
```

---

## План внедрения (4 фазы)

### Фаза 1: Создание профиля (2-3 часа)
- [ ] Создать `~/.hermes/profiles/alikhan/`
- [ ] Написать SOUL.md
- [ ] Скопировать AGENTS.md из основного проекта
- [ ] Сконфигурировать config.yaml (провайдер, без X MCP)
- [ ] Перенести 8 alikhan-навыков в профиль
- [ ] Перенести память (выделить alikhan-специфичные записи)

### Фаза 2: Перенос cron-задач (1-2 часа)
- [ ] ЕЖО авто-шаблон (8:00 Бишкек)
- [ ] Снимок дня (авто 18:00 или по запросу)
- [ ] Погода (1:30 и 10:30 UTC)
- [ ] CHRONOLOGY sync (из WhatsApp в Git)
- [ ] Health check (каждые 30 минут)

### Фаза 3: Автономный запуск (1 час)
- [ ] systemd unit: `hermes-profile-alikhan.service`
- [ ] Запуск при старте VPS
- [ ] Restart=always
- [ ] Тестирование автономной работы

### Фаза 4: Шаблон для клонирования (1 час)
- [ ] Документировать процесс клонирования
- [ ] Создать скрипт `clone_alikhan_profile.sh`
- [ ] Подготовить список object-specific параметров

---

## Метрики успеха

| Метрика | Текущее | Цель |
|---------|---------|------|
| Автономность Alikhan | 0% (всё через основной Hermes) | 95% |
| Время на развёртывание клона | Невозможно | 30 минут |
| Самостоятельное исправление багов | 0 | 80% типовых багов |
| Uptime младшего Hermes | N/A | 99.5% |

---

## Риски

| Риск | Вероятность | Митигация |
|------|-----------|----------|
| Младший Hermes само-поломает код | Средняя | Pre-commit gate + git history + откат |
| Конфликт ресурсов с основным | Низкая | Разные профили, разные cron-слоты |
| Перерасход токенов на Grok | Средняя | Budget guard в конфиге |
| Разные Hermes-версии у основного и младшего | Низкая | Один `hermes update` для всех профилей |
