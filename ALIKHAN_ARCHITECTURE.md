# ALIKHAN ARCHITECTURE — Правила, которые нельзя нарушать

> **Назначение:** этот документ — единый источник правды для всех агентов Alikhan. Здесь описана логика проекта, которую агент ДОЛЖЕН знать перед любой правкой. Нарушение любого правила = откат.

## ⛔ ПРАВИЛО №0: Перед любой правкой

1. Прочитать CHRONOLOGY.md — последние 50 строк
2. Запросить Knowledge Graph: `python3 ~/Alikhan-migration/knowledge_graph/query_tool.py grounded_answer "What recurring bugs affect <component> right now?"`
3. MoA: Codex (Maker) → Grok (Checker) → применять только после PASS
4. Показать grep всех затрагиваемых функций/переменных

## 1. Табель АйБиКон (data_sources.py:618, get_aibikon_headcount)

### Структура листа «Табель»:
- Колонка 1: № п/п
- Колонка 2: ФИО
- Колонка 3: Должность
- Колонки 5+: дни месяца (1-31)
- День месяца → колонка = 5 + день − 1

### Цвета заливки:
- **theme=0 (чёрный фон) = ВЫХОДНОЙ**
- **theme=7 (жёлтый/зелёный) = РАБОЧИЙ**
- **patternType='solid' + theme != 0 = человек на площадке**

### PROF_MAP (должности):
| Код в табеле | Каноническое название |
|-------------|---------------------|
| рук.проекта | Руководителя строительства |
| зам.рук.проекта | Руководителя строительства |
| геодезист | Инженер геодезист |
| тб | Инженер ТБ и ОТ |
| пто | Инженер ПТО |
| электрик | Электрик |

### Фильтры строк:
- Пропускать: «фио», «директор», «руководител», «согласовано», «и.о.рук»
- Считать только строки с № ≥ 1
- Пропускать: val = «отпуск», «отп», «больничный»

### НЕ ТРОГАТЬ:
- Условие `fill.patternType == 'solid' and fill.fgColor.theme is not None and fill.fgColor.theme != 0`

## 2. get_staff (data_sources.py:263)

### Источник: ojr_section1_personnel (active window: start_date <= d AND end_date IS NULL OR end_date >= d)

### Нормализация должностей:
- ИТР: «инженер», «геодезист», «электрик», «рук.», «руководител», «рук стр» → norm_pos = «итр»
- Рабочие: «рабочий», «рабочие», «работник» → norm_pos = «рабочие»
- Прораб: «прораб» → norm_pos = «прораб»
- Машинист: «машинист» → norm_pos = «машинист»

### Dedup: DISTINCT ON (org, norm_pos) ORDER BY start_date DESC, wc DESC

### НЕ ДОБАВЛЯТЬ reliable_orgs/filtered CTE — это ломает табель АйБиКон!

### Схема АйБиКон в personnel:
- sync_source='ejo_v2': детальные должности (workers_count=1 каждая)
- sync_source='qa': агрегированные (ИТР=3, workers_count=3)

## 3. WhatsApp Bridge (bridge.js)

### Критические поля:
- /health → collectOnlyChats: [] (WHATSAPP_SANDBOX + WHATSAPP_PRODUCTION)
- GET /collect-messages?only=<JID> → возвращает сообщения только для указанного чата

### Диспетчер (whatsapp_commands.py:151):
- Без collectOnlyChats в health → тик пропущен
- Читает через /collect-messages?only=PRODUCTION

### После обновления hermes-agent:
- bridge.js сбрасывается → нужен перезапуск gateway
- НЕ перезапускать gateway без согласования с Сергеем

## 4. ЕЖО (fill_ejo.py)

### После успешной генерации:
- shutil.copy2(out_path, TEMPLATE_PATH) — обновляет шаблон для опроса
- TEMPLATE_PATH = ~/Alikhan-migration/bot/templates/ЕЖО_шаблон.xlsx

### Опрос читает TEMPLATE, не /tmp

## 5. Инфраструктура

### WhatsApp мост:
- Управляется gateway-адаптером, НЕ systemd-юнитом
- health-check: curl :3000/health (не systemctl status)
- Юнит намеренно disabled

### Ночная проверка (cron ffcc5f112fff):
- Проверяет через curl :3000/health
- Запрещено systemctl enable/start

## 6. Известные баги и ловушки

| Компонент | Баг | Фикс |
|-----------|-----|------|
| get_staff | reliable_orgs CTE отбрасывает ejo_v2 | Не добавлять reliable_orgs |
| Табель | theme=0 считается рабочим | theme != 0 обязательно |
| Опрос | Старые остатки из TEMPLATE | fill_ejo копирует в TEMPLATE |
| Bridge | collectOnlyChats пропадает после обновления | Патч bridge.js + перезапуск gateway |
| Bridge | /messages крадёт сообщения у /collect-messages | /messages заглушен (deprecated) |

## 7. MoA — Процедура изменений

1. Я (Hermes) анализирую проблему, читаю CHRONOLOGY + KG
2. Codex CLI: пишет код
3. Grok Build CLI: adversarial review, ищет баги
4. Если Grok FAIL → Codex исправляет → Grok снова
5. Только после Grok PASS → commit
