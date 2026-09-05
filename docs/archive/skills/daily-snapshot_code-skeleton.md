# generate_daily_snapshot — code skeleton with all None-guards (17.07.2026)

## Critical: return statement

The function MUST end with `return result`. Without it, `send_msg` receives `None` and crashes on `text[:3800]` with `TypeError: 'NoneType' object is not subscriptable`.

```python
def generate_daily_snapshot(chat_id):
    # ... all data collection ...
    result = f"📅 Снимок дня {today_str}\n...\n{narrative}"
    return result    # ← REQUIRED. Missing = crash.
```

## Photo extraction — guard mid/content NULL

```python
photos = []
for r in photos_raw:
    d = r['desc']
    if not d:
        mid_val = r.get('mid')              # content column can be NULL
        d = f"фото {mid_val[:8]}" if mid_val else "фото (без ID)"
    photos.append((r['bld'] or 'общий', d))
photos = photos[:10]
```

## Poll data — guard pdata against NULL

```python
if poll:
    pdata = poll['data']              # can be None (NULL in DB)
    if isinstance(pdata, str):
        pdata = json.loads(pdata)
    collected = pdata.get('collected', {}) if isinstance(pdata, dict) else {}
    if collected:
        # ... iterate items ...
    else:
        poll_info = (
            f"Опрос: статус {pdata.get('poll', {}).get('status', '?')}, собрано 0 позиций"
            if isinstance(pdata, dict) else "опрос не проводился"
        )
```

## Weather — weatherDesc directly, guard current_condition

```python
weather = "погода недоступна"
try:
    r = requests.get("https://wttr.in/42.2,72.5?format=j1&lang=ru", timeout=10)
    if r.status_code == 200:
        data = r.json()
        current = data.get('current_condition') or [{}]
        c = current[0] if current else {}        # guard: current can be []
        temp = c.get('temp_C', 'N/A')
        wd = c.get('weatherDesc') or [{}]
        desc = wd[0].get('value', '') if wd else ''
        wind = c.get('windspeedKmph', 'N/A')
        weather = f"{desc}, +{temp}°C, ветер {wind} км/ч"
except:
    pass
```

**DO NOT use `lang_ru` key** — despite `lang=ru` in URL, it can be null. Use `weatherDesc[0].value` directly.

## Ollama model check

```bash
# Verify model matches handlers.py
grep OLLAMA_MODEL /home/hermes-workspace/Alikhan-migration/bot/handlers.py
ollama list | grep qwen
```

Mismatch = silent xAI fallback = wasted tokens. Fix: update `OLLAMA_MODEL` to match installed model.
