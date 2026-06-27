#!/usr/bin/env python3
"""Simulate 10 EJO questions with speech defects (STT errors) and test Grok correction + routing."""

import sys, os, re, json
from datetime import datetime

sys.path.insert(0, "/home/hermes-workspace/Alikhan-migration/bot")

VOICE_TRIGGERS = ["голосом", "озвучь", "голос"]
SANDBOX = "120363179621030401@g.us"

def is_qa(text):
    if "?" in text or any(w in text.lower() for w in
       ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему", "что", "как"]):
        return False
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "сделано", "не успели", "техник"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    return bool(re.search(r'\d\.\d\.\d+\s*=', text))

def ali_match(text):
    return bool(re.search(r'[ао]л[еи][хгк]', text.lower()))

from handlers import ask_grok

def grok_correct(raw):
    """Simulate the Grok correction step from main_waha.py"""
    corrected = ask_grok(
        f"Исправь опечатки и ошибки распознавания в тексте. "
        f"Скорее всего там имя «Алихан» (голосовой ассистент). "
        f"Также исправь искажённые вопросные слова: такая→какая, такой→какой, че→что, скока→сколько. "
        f"Верни ТОЛЬКО исправленный текст, без пояснений:\n\n{raw}",
        max_tokens=200
    ).strip()
    return corrected if corrected else raw

def db_fact_lookup():
    try:
        from db_memory import fact_lookup
        today = datetime.now().strftime("%Y-%m-%d")
        return fact_lookup(SANDBOX, start_date=today, limit=5)
    except:
        return []

def route(text):
    """Full bot routing pipeline"""
    # 1. QA check
    if is_qa(text):
        return "QA", "✅ Принято: факты сохранены в БД"
    
    # 2. Alikhan check
    if not ali_match(text):
        return "IGNORE", "(сохранено в БД, без ответа)"
    
    # 3. Weather
    if any(w in text.lower() for w in ["погод", "температур", "ветер", "давлени", "осадк"]):
        try:
            import urllib.request as _ur
            wreq = _ur.Request(
                "https://api.open-meteo.com/v1/forecast?latitude=42.284&longitude=72.765"
                "&current=temperature_2m,wind_speed_10m,relative_humidity_2m,pressure_msl,weather_code"
                "&timezone=Asia/Bishkek&forecast_days=1"
            )
            wdata = json.loads(_ur.urlopen(wreq, timeout=10).read())
            c = wdata.get("current", {})
            wmo = {0:"Ясно",1:"Ясно",2:"Переменная облачность",3:"Пасмурно",45:"Туман",48:"Иней",
                   51:"Морось",53:"Морось",55:"Морось",61:"Дождь",63:"Дождь",65:"Ливень",
                   71:"Снег",73:"Снег",75:"Снег",80:"Ливень",95:"Гроза",96:"Гроза с градом",99:"Гроза с градом"}
            return "WEATHER", (
                f"🌤 Джеруй: {wmo.get(c.get('weather_code',0),'?')}, "
                f"{c.get('temperature_2m','?')}°C, "
                f"ветер {c.get('wind_speed_10m','?')} м/с"
            )
        except:
            return "GROK", "(погода недоступна)"
    
    # 4. DB facts
    factual_words = ["рабочих", "техник", "статус", "что сегодня", "происшестви", "итог", "подведи", "сделано", "персонал"]
    if any(w in text.lower() for w in factual_words):
        facts = db_fact_lookup()
        if facts:
            lines = [f"• {f['category']}: {str(f['fact'])[:60]}" for f in facts[:3]]
            return "DB", "📋 Сегодня:\n" + "\n".join(lines)
        return "DB_EMPTY", "📋 Данных за сегодня нет."
    
    # 5. Grok
    return "GROK", "(ответ Grok)"


# ── 10 questions WITH speech defects ──
tests = [
    # (description, raw_stt_output, expected_routing)
    ("👄 «Алейхам» → Алихан",          "Алейхам, какая техника работает", "DB"),
    ("👄 «Олеган» → Алихан",           "Олеган, сколько рабочих сегодня", "DB"),
    ("👄 «такая→какая»",               "Алихан, такая погода на объекте", "WEATHER"),
    ("👄 «скока→сколько»",             "Алихан, скока рабочих на абк", "DB"),
    ("👄 «Аллехан» → Алихан",          "Аллехан, что сделано сегодня", "DB"),
    ("👄 «Олег Ант» → Алихан",         "Олег Ант, подведи итоги", "DB"),
    ("👄 «Аликан» → Алихан",           "Аликан, какая техника на объекте", "DB"),
    ("👄 «че→что» + персонал",         "Алихан, че по персоналу сегодня", "DB"),
    ("👄 данные без «алихан»",         "атантай 5 рабочих ИТР 2", "QA"),
    ("👄 «Лехан» → Алихан + погода",   "Лехан, погода на джеруе", "WEATHER"),
]

print("=" * 70)
print("СИМУЛЯЦИЯ С ДЕФЕКТАМИ РЕЧИ (STT → Grok → Routing)")
print("=" * 70)

passed = 0
failed = 0

for i, (desc, raw, expected) in enumerate(tests, 1):
    # Step 1: Grok correction
    corrected = grok_correct(raw)
    
    # Step 2: Route
    action, reply = route(corrected)
    
    ok = action == expected
    if ok:
        passed += 1
    else:
        failed += 1
    
    icon = "✅" if ok else "❌"
    print(f"\n── {i}. {desc} {icon}")
    print(f"   🎤 raw:      {raw}")
    print(f"   🤖 corrected: {corrected}")
    print(f"   🔀 route:     {action} (expected: {expected})")
    print(f"   📤 reply:     {reply[:100]}")

print("\n" + "=" * 70)
print(f"Результат: {passed}/{passed+failed} passed")
if failed == 0:
    print("🎉 Все дефекты речи исправлены, маршрутизация верна!")
else:
    print(f"⚠️  {failed} ошибок маршрутизации")
print("=" * 70)
