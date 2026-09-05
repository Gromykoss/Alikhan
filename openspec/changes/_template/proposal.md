# OpenSpec Change Template

## proposal.md
```markdown
# Change: <краткое название>

## Why
<проблема / мотивация>

## What Changes
- <домен> → <что меняется>

## Affected Domains
- <карточка openspec/specs/*.md>

## Impact
- Инварианты затрагиваются? (да/нет, какие)
- Тесты: <какие обновятся/добавятся>
```

## design.md
```markdown
# Design: <название>

## Approach
<выбранный подход + альтернативы>

## Data / Schema
<если затрагивает БД — точные изменения>

## Risks
- <риск> → <митигация>
```

## tasks.md
```markdown
# Tasks
- [ ] <шаг 1>
- [ ] <шаг 2>
- [ ] Обновить карточку openspec/specs/<домен>.md
- [ ] Обновить PROJECT_MEMORY_GRAPH.md (или запись 'Contract index update: not needed')
- [ ] pytest bot/ -q зелёный
```
