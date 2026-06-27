"""DB lookup module: fact_lookup + weather API"""
import json, urllib.request
from datetime import datetime

def lookup_facts(chat_id, text):
    """Returns (db_reply, weather_reply) — each may be None."""
    db_reply = None
    weather_reply = None

    # Weather
    if any(w in text.lower() for w in ["погод", "температур", "ветер", "давлени", "осадк"]):
        try:
            wreq = urllib.request.Request(
                "https://api.open-meteo.com/v1/forecast?latitude=42.284&longitude=72.765"
                "&current=temperature_2m,wind_speed_10m,relative_humidity_2m,pressure_msl,weather_code"
                "&timezone=Asia/Bishkek&forecast_days=1"
            )
            wdata = json.loads(urllib.request.urlopen(wreq, timeout=10).read())
            c = wdata.get("current", {})
            wmo = {0:"Ясно",1:"Ясно",2:"Переменная облачность",3:"Пасмурно",45:"Туман",48:"Иней",
                   51:"Морось",53:"Морось",55:"Морось",61:"Дождь",63:"Дождь",65:"Ливень",
                   71:"Снег",73:"Снег",75:"Снег",80:"Ливень",95:"Гроза",96:"Гроза с градом",99:"Гроза с градом"}
            weather_reply = (
                f"🌤 Джеруй: {wmo.get(c.get('weather_code',0),'?')}, "
                f"{c.get('temperature_2m','?')}°C, "
                f"ветер {c.get('wind_speed_10m','?')} м/с, "
                f"{c.get('relative_humidity_2m','?')}%, "
                f"{round(c.get('pressure_msl',0)*0.75006)} мм рт.ст."
            )
        except Exception as e:
            print(f"[WEATHER ERR] {e}", flush=True)

    # DB facts
    factual_words = ["рабочих", "техник", "статус", "что сегодня", "происшестви",
                      "итог", "подведи", "сделано", "персонал", "итр", "инженер"]
    if any(w in text.lower() for w in factual_words):
        try:
            from db_memory import fact_lookup
            today_str = datetime.now().strftime("%Y-%m-%d")
            cat_filter = None
            if any(w in text.lower() for w in ["рабочих", "персонал", "сколько человек", "итр", "инженер"]):
                cat_filter = "персонал"
            elif any(w in text.lower() for w in ["техник", "оборудован", "машин"]):
                cat_filter = "техника"
            facts = fact_lookup(chat_id, start_date=today_str, limit=10, category=cat_filter)
            if facts:
                lines = [f"{f['category']}: {f['fact']} ({f['building']})" for f in facts]
                db_reply = "📋 Сегодня:\n" + "\n".join(lines)
        except Exception as e:
            print(f"[DB LOOKUP ERR] {e}", flush=True)

    return db_reply, weather_reply
