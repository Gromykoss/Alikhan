# Obsidian Kanban Boards

Session: 2026-06-28 — создание 3 раздельных досок для Алихан, Система, Crypto.

## Формат файла

```markdown
---
kanban-plugin: board
---

## 💡 Идеи

- [ ] Task title

## 🔍 Анализ

- [ ] Task in analysis

## ⚙️ В работе

- [ ] Active task

## 👁 На проверке

- [ ] Review task

## ✅ Готово

- [x] Completed task

## ❌ Архив

- [x] Archived task
```

## Размещение в vault

- `6-System/Dashboards/Система.md` — инфраструктура, VPS, Hermes, идеи
- `20_Projects/Hermes/Алихан Kanban.md` — WhatsApp бот, голос, график
- `20_Projects/Hermes/Crypto Kanban.md` — RAB9/Crypto, loop catalog

## Синхронизация

Файлы Kanban — обычные .md файлы. После изменений на VPS: `git add + commit + push`. Пользователь делает `Obsidian Git: Pull` в Obsidian.

⚠️ Если пользователь создаёт Kanban-доски локально в Obsidian и НЕ коммитит их, при pull возникают конфликты (`Untitled Kanban.md`, `Untitled Kanban 1.md`, etc). Решение: либо закоммитить локальные доски до pull, либо удалить их через Obsidian UI перед pull.

## Hermes Kanban CLI (отдельная система)

Hermes имеет собственную Kanban-систему (SQLite, отдельная от Obsidian). Используется для авто-диспатчинга задач через gateway.

### Синтаксис

```bash
# Правильно — --board ПОСЛЕ kanban
hermes kanban --board system list
hermes kanban --board alikhan create --triage "Title" --body "Description"

# Неправильно — --board ДО kanban
hermes --board system kanban list  # ❌ не работает
```

### Управление досками

```bash
hermes kanban boards list                    # список досок
hermes kanban boards create <slug>           # создать
hermes kanban boards rename <slug> "Name"    # переименовать
hermes kanban boards switch <slug>           # переключить (⚠️ не всегда надёжно)
hermes kanban boards rm <slug> --delete      # удалить
```

### Pitfalls

- `boards switch` не всегда сохраняет контекст между вызовами — надёжнее использовать `--board <slug>` явно
- Default-доска не удаляется
- Диспатчер gateway авто-запускает задачи из triage → todo → running без подтверждения
- `--triage` паркует задачу, но specifier может сразу промоутнуть её в running
