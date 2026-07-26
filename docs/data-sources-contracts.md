# data_sources.py — контракты данных для ЕЖО

## Цель

Вынести ВСЕ обращения к БД, API, файловой системе из fill_ejo.py в единый модуль `data_sources.py`.
fill_ejo.py использует **только** функции из data_sources и **никогда** не ходит напрямую в:
- `db.get_conn()`
- `bot_memory_facts`
- `bot_memory_messages`
- `ojr_*` таблицы
- `requests` (Open-Meteo)
- `glob` (табель, старые ЕЖО)
- `os.path.exists` для файлов данных

## Контракты (NamedTuple)

```python
from typing import NamedTuple

class WeatherData(NamedTuple):
    temp: str        # "18°C" или "—"
    wind: str        # "СВ 5,2 км/ч" или "—"
    humidity: str    # "65%" или "—"
    pressure: str    # "712 мм рт.ст." или "—"
    visibility: str  # "10+ км" или "—"

class IncidentCount(NamedTuple):
    count: str       # "0" или "2"

class StaffOrg(NamedTuple):
    total: int
    itr: int
    workers: int

class StaffData(NamedTuple):
    orgs: dict[str, StaffOrg]  # ключ: "Атантай", "Майкадам", "Наватек", "Алтын-Тас", "АйБиКон"
    # Всегда содержит ключи для 4 известных субподрядчиков (даже с нулями)

class VolumeData(NamedTuple):
    works: dict[str, float]  # code→объём (только работы, не планы)
    plans: dict[str, float]  # code→объём (только планы)
    # works и plans — взаимоисключающие

class PhotoCount(NamedTuple):
    building: str
    count: int

class PhotoFile(NamedTuple):
    building: str
    msg_id: str        # WhatsApp message ID (для bridge_wrapper)
    local_path: str    # путь к файлу в кеше

class PhotoData(NamedTuple):
    counts: dict[str, int]  # building→кол-во фото
    files: list[PhotoFile]  # список для вставки в ЕЖО

class AIBHeadcount(NamedTuple):
    total: int
    by_prof: dict[str, int]  # профессия→кол-во
    is_fallback: bool

class EquipmentData(NamedTuple):
    items: dict[str, int]  # название→кол-во

class MaterialItem(NamedTuple):
    name: str
    qty: str
    unit: str

class MaterialData(NamedTuple):
    items: list[MaterialItem]

class ActivePhases(NamedTuple):
    phases: set[int]

class PlanData(NamedTuple):
    plans: dict[str, float]  # code→объём

class CodeSource(NamedTuple):
    """Коды работ из последнего сгенерированного ЕЖО."""
    codes: dict[str, tuple[str, str, str]]  # code→(building, name, unit)
```

## Функции (интерфейс)

```python
def get_weather(date: datetime) -> WeatherData
def get_incidents(date: datetime) -> IncidentCount
def get_staff(date: datetime) -> StaffData
def get_volumes(date: datetime) -> VolumeData
def get_photos(date: datetime) -> PhotoData
def get_aibikon_headcount(date: datetime = None) -> AIBHeadcount
def get_equipment(date: datetime) -> EquipmentData
def get_materials(date: datetime) -> MaterialData
def get_active_phases(date: datetime) -> ActivePhases
def get_plans_from_messages(date: datetime) -> PlanData
def get_code_source() -> CodeSource | None
```

## Правила реализации

1. Каждая функция оборачивает primary source в try/except с fallback на legacy
2. Формат лога: `[DS {FUNC}] ...` и `[DS {FUNC} ERR] ... falling back`
3. db.get_conn() импортируется ОДИН раз вверху модуля
4. Никаких print() без префикса `[DS ...]`
5. Все SQL-запросы используют параметризацию (`%s`, не f-строки)
6. Функции НЕ имеют побочных эффектов (кроме save_weather — сохраняет, но это идемпотентно)

## Миграция fill_ejo.py

После создания data_sources.py, fill_ejo.py должен:
1. Импортировать: `from data_sources import *`
2. Удалить функции: `weather()`, `incidents()`, `staff()`, `volumes()`, `photos()`, `get_aibikon_headcount()`, `get_active_phases()`, `get_code_source()`, `parse_plans_from_raw_messages()`, `qa()`, `db()`
3. Заменить все вызовы:
   - `weather(date)` → `get_weather(date)`
   - `incidents(date)` → `get_incidents(date).count`
   - `staff(date)` → `get_staff(date).orgs`
   - `volumes(date)` → `get_volumes(date)` (доступ к .works и .plans)
   - `photos(date)` → `get_photos(date)` (доступ к .counts и .files)
   - `get_aibikon_headcount(date)` → `get_aibikon_headcount(date)` (интерфейс совместимый)
   - `get_active_phases(date)` → `get_active_phases(date).phases`
   - `get_code_source()` → `get_code_source()` (интерфейс совместимый)
   - `parse_plans_from_raw_messages(date)` → `get_plans_from_messages(date).plans`
4. Адаптировать обращения к staff: `stf.get('Атантай', {})` → `stf.get('Атантай')` (теперь StaffOrg, не dict)
5. Адаптировать volumes: `vols_all, plans, dn = volumes(date)` → `vd = get_volumes(date); vd.works, vd.plans`
6. Адаптировать photos: `photos(date)['Общежитие']` → `get_photos(date).counts['Общежитие']`
7. Адаптировать вставку фото: вместо прямого SQL — использовать `get_photos(date).files`

## НЕ трогать

- `fill_ejo.py`: функции `fill()`, `_hide_rows()`, `calc_completion_pct()`, `sw()`, `yellow()`, `set_fill()`, `yesterday_cum()`, `parse_number()`, `_get_aibikon_from_ojr()`
- `bridge_wrapper.py`
- Все остальные файлы бота
