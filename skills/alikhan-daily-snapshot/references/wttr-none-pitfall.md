# wttr.in NoneType pitfall (17.07.2026)

## Symptom
`NoneType object is not subscriptable` при генерации снимка дня.

## Root cause
```python
c = data.get('current_condition', [{}])[0]
```
Если API вернул `"current_condition": null`, то `.get()` возвращает `None` (default применяется только при отсутствии ключа).

То же самое с `lang_ru`.

## Fix
```python
current = data.get('current_condition') or [{}]
c = current[0] if current else {}

lang_ru = c.get('lang_ru') or []
desc = lang_ru[0].get('value', '') if lang_ru else c.get('weatherDesc', [{}])[0].get('value', '')
```