#!/usr/bin/env python3
"""Simulate 10 EJO voice questions to Alikhan and analyze responses."""

import sys, os, re, json
from datetime import datetime

sys.path.insert(0, "/home/hermes-workspace/Alikhan-migration/bot")

# ── Simulate the bot's processing pipeline ──

VOICE_TRIGGERS = ["голосом", "озвучь", "голос"]
SANDBOX = os.environ.get("WHATSAPP_SANDBOX", "")

def is_qa(text):
    """Same logic as main_waha.py"""
    if "?" in text or any(w in text.lower() for w in
       ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему", "что"]):
        return False
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "сделано", "не успели", "техник"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    return bool(re.search(r'\d\.\d\.\d+\s*=', text))

def ali_match(text):
    """Fuzzy match for 'алихан'"""
    return bool(re.search(r'[ао]л[еи][хгк]', text.lower()))

def has_voice_trigger(text):
    return any(w in text.lower() for w in VOICE_TRIGGERS)

def db_fact_lookup():
    """Get today's facts from DB"""
    try:
        from db_memory import fact_lookup
        today = datetime.now().strftime("%Y-%m-%d")
        return fact_lookup(SANDBOX, start_date=today, limit=5)
    except:
        return []

def ask_bot(text):
    """Simulate full bot pipeline and return (action, reply)"""
    
    # 1. Check QA
    if is_qa(text):
        return "QA", "✅ Принято: факты сохранены в БД"
    
    # 2. Check if addressed to Alikhan
    if not ali_match(text):
        return "IGNORE", "(сохранено в БД, без ответа)"
    
    # 3. Weather API
    weather_words = ["погод", "температур", "ветер", "давлени", "осадк"]
    if any(w in text.lower() for w in weather_words):
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
                f"ветер {c.get('wind_speed_10m','?')} м/с, "
                f"{c.get('relative_humidity_2m','?')}%, "
                f"{round(c.get('pressure_msl',0)*0.75006)} мм рт.ст."
            )
        except:
            return "GROK", "(погода недоступна)"

    # 4. DB lookup for factual questions
    factual_words = ["рабочих", "техник", "статус", "что сегодня", "происшестви", "итог", "подведи", "сделано"]
    if any(w in text.lower() for w in factual_words):
        facts = db_fact_lookup()
        if facts:
            lines = [f"  • {f['category']}: {str(f['fact'])[:80]} ({f.get('building','?')})" for f in facts]
            return "DB", "📋 Сегодня:\n" + "\n".join(lines)
        else:
            return "DB_EMPTY", "📋 Данных за сегодня нет."
    
    # 4. Grok
    from handlers import ask_grok
    prompt = (
        f"Ты — строительный инспектор на площадке ТЗРК Джеруй (Кыргызстан, горы, ~2700м). "
        f"Строятся: АБК (2 этажа), Общежитие (3 этажа), Галерея. "
        f"Сегодня {datetime.now().strftime('%d.%m.%Y, %A')}. "
        f"Если вопрос про факты (техника, рабочие, происшествия) — скажи что нужно уточнить в БД. "
        f"Отвечай как прораб: коротко, по делу, без воды.\n\n"
        f"Вопрос: {text}"
    )
    reply = ask_grok(prompt, max_tokens=200).strip()
    return "GROK", reply


# ── 10 EJO Test Questions ──

questions = [
    # 1. Personnel data (should go to QA, not a question)
    ("QA: персонал", "алихан атантай 5 рабочих ИТР 2 человека"),
    
    # 2. Equipment data (should go to QA)
    ("QA: техника", "алихан наватек экскаватор 1 самосвал 2"),
    
    # 3. Question about workers (should go to DB)
    ("Вопрос: рабочие", "алихан сколько сегодня рабочих на объекте"),
    
    # 4. Question about equipment (should go to DB)
    ("Вопрос: техника", "алихан какая техника работает сегодня"),
    
    # 5. Incident report (QA data)
    ("QA: инцидент", "алихан происшествий нет сделано по плану"),
    
    # 6. Weather question (Grok — general knowledge)
    ("Вопрос: погода", "алихан какая сегодня погода на джеруе"),
    
    # 7. Work progress (Grok — but could be DB)
    ("Вопрос: работы", "алихан что сегодня сделано на объекте"),
    
    # 8. VOR code (QA)
    ("QA: VOR", "алихан 2.1.5 = 100м3 бетон"),
    
    # 9. Summary request (DB)
    ("Вопрос: итоги", "алихан подведи итоги за сегодня"),
    
    # 10. Message without addressing Alikhan (should be ignored)
    ("Без имени", "сколько сегодня рабочих на абк"),
]

print("=" * 70)
print("СИМУЛЯЦИЯ: 10 голосовых вопросов по ЕЖО")
print("=" * 70)

results = []

for i, (category, text) in enumerate(questions, 1):
    action, reply = ask_bot(text)
    lines = reply.split("\n")
    first_line = lines[0][:80]
    
    print(f"\n── {i}. [{category}] ──")
    print(f"   📥 {text[:70]}")
    print(f"   🔀 {action}", end="")
    if action == "IGNORE":
        print(" (нет «алихан»)")
    elif action == "QA":
        print(" → QA-парсер")
    elif action == "DB":
        print(" → БД")
    elif action == "DB_EMPTY":
        print(" → БД (пусто)")
    elif action == "GROK":
        print(" → Grok")
    print(f"   📤 {first_line}")
    if len(lines) > 1:
        for l in lines[1:6]:
            print(f"      {l[:80]}")
    
    results.append((category, action, reply))

# ── Analysis ──
print("\n" + "=" * 70)
print("АНАЛИЗ")
print("=" * 70)

qa_count = sum(1 for _, a, _ in results if a == "QA")
db_count = sum(1 for _, a, _ in results if a == "DB")
grok_count = sum(1 for _, a, _ in results if a == "GROK")
ignore_count = sum(1 for _, a, _ in results if a == "IGNORE")
db_empty_count = sum(1 for _, a, _ in results if a == "DB_EMPTY")
weather_count = sum(1 for _, a, _ in results if a == "WEATHER")

print(f"""
Распределение:
  QA (данные)     : {qa_count}/10
  DB (факты)      : {db_count}/10
  WEATHER (погода): {weather_count}/10
  Grok (общее)    : {grok_count}/10
  Игнор (без имени): {ignore_count}/10
""")

# Detailed analysis
print("Детальный разбор:")
for i, (cat, action, reply) in enumerate(results, 1):
    icon = "✅" if action in ("QA", "DB", "IGNORE") else "⚠️"
    if action == "DB_EMPTY":
        icon = "ℹ️"
    note = ""
    if "персонал" in cat.lower() or "рабочие" in cat.lower():
        note = " — данные из БД" if action == "DB" else " — ожидался DB-ответ"
    if "техника" in cat.lower():
        note = " — данные из БД" if action == "DB" else " — ожидался DB-ответ"
    if "без имени" in cat.lower():
        note = " — правильно проигнорирован" if action == "IGNORE" else " — должен был проигнорировать"
    print(f"  {icon} {i}. [{cat}] → {action}{note}")

print("\nВывод: проверь ответы выше — корректно ли бот отвечает на каждый вопрос?")
