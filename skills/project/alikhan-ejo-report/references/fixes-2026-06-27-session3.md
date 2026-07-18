# Fixes — 2026-06-27 Session 3

Исправления в `fill_ejo.py` и `smart_evening_check.py` по итогам заполнения ЕЖО 26.06.2026.

## fill_ejo.py

### 1. Очистка старых материалов (Лист 4, R8-R9)

**Проблема:** QA сказал «поставок материалов не планируется», но в отчёте остался «Грунт для обратной засыпки | м3 | 472» из шаблона.

**Исправление:** всегда очищать rows 8-9 cols 2-6 на «—», если нет новых парсируемых данных:

```python
mat_facts = [f['fact'] for f in qa(date, 'документация') if 'материал' in (f.get('fact','') or '').lower()]
if mat_facts and not any('не планируется' in f.lower() or 'нет' in f.lower() for f in mat_facts):
    pass  # TODO: parse material quantities
# Clear old template values unconditionally
for row in [8, 9]:
    for c in [2, 3, 4, 5, 6]:
        cell = ws.cell(row=row, column=c)
        if yellow(cell) or (cell.value is not None and str(cell.value).strip() not in ['—', 'None', '']):
            sw(ws, row, c, '—', True)
```

### 2. Обрезка текста планов (Лист 4, колонка B)

**Проблема:** «Армирование арматурой ø8А500С с шагом 200 мм плиты перекрытия в осях А-Г/1-10» не влезает в ячейку.

**Исправление:** `nm[:35]` при записи в колонку B.

### 3. Очистка колонки F для пустых строк планов

**Проблема:** для АБК нет планов → R19F показывает старый остаток из шаблона.

**Исправление:** добавить `sw(ws, row, 6, '—', True)` в else-блок:

```python
else:
    sw(ws, row, 1, '—', True); sw(ws, row, 2, '—', True)
    sw(ws, row, 3, '—', True); sw(ws, row, 4, '—', True)
    sw(ws, row, 6, '—', True)  # clear leftover остаток
```

### 4. Сброс жёлтой заливки в колонке L

**Проблема:** строка 55 (код 2.4.2) сохраняет жёлтый PatternFill из шаблона в L55.

**Исправление:** после заполнения объёмов:

```python
from openpyxl.styles import PatternFill
no_fill = PatternFill(fill_type=None)
for r in range(24, ws.max_row+1):
    for c in [12]:  # column L
        cell = ws.cell(r, c)
        if yellow(cell) and str(cell.value).strip() in ['—', 'None', '']:
            cell.fill = no_fill
```

## smart_evening_check.py

### Добавлены секции 6 (Планы) и 7 (Материалы)

Секция 6 показывает топ-5 ВОР-кодов с остатками по каждому зданию и запрашивает планы в формате «План код = объём».

Секция 7 запрашивает материалы. Категория `'материалы'` добавлена в `get_qa_status()`.

## Self-verify: уточнения

- B35-B37 — заголовки «Статистика по технике»/«Наименование», None нормально (не данные)
- R8-R9 материалы — должны быть «—» (не старые значения шаблона)
- R19F (и аналогичные) — «—» когда нет планов для здания
- `len(ws._images)` — проверять соответствие количеству фото в БД (макс 3 на здание)
- QA-коды бетонирования должны присутствовать в Col3 шаблона (иначе объёмы молча не заполнятся)
