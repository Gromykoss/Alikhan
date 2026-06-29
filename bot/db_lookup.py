"""DB lookup module: fact_lookup + weather API"""
import json, urllib.request
from datetime import datetime

def lookup_facts(chat_id, text):
    """Returns (db_reply, weather_reply) — each may be None."""
    db_reply = None
    weather_reply = None

    # Weather — extended stems for STT errors (пагод→погод, etc.)
    if any(w in text.lower() for w in ["погод", "пагод", "температур", "ветер", "давлени", "осадк"]):
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


def lookup_schedule(chat_id, text):
    text_l = text.lower()
    # Extended stems for STT errors: атставан→отставан, etc.
    triggers = ["график", "этап", "отставан", "атставан", "срок", "план",
                "календарный", "отклонени", "атклонени",
                "задержк", "опережен"]
    if not any(t in text_l for t in triggers):
        return None
    try:
        from db import get_schedule, get_active_phases, get_upcoming_phases, check_delays
        if any(w in text_l for w in ["отставан", "задержк", "отклонени"]):
            delays = check_delays()
            if not delays:
                return "✅ Отставаний по графику нет."
            lines = []
            for d in delays:
                ed = d['end_date'].strftime('%d.%m.%Y') if hasattr(d['end_date'], 'strftime') else str(d['end_date'])
                lines.append(f"⚠️ {d['phase_name']} — план до {ed}")
            return "📅 Отставания:\n" + "\n".join(lines)
        elif any(w in text_l for w in ["активн", "идут", "сейчас", "текущ"]):
            active = get_active_phases()
            if not active:
                return "Активных этапов нет."
            lines = []
            for a in active:
                sd = a['start_date'].strftime('%d.%m.%Y') if hasattr(a['start_date'], 'strftime') else str(a['start_date'])
                ed = a['end_date'].strftime('%d.%m.%Y') if hasattr(a['end_date'], 'strftime') else str(a['end_date'])
                lines.append(f"• {a['phase_name']} — {sd}–{ed} ({a['duration_days']} дн.)")
            return "📅 Активные этапы:\n" + "\n".join(lines)
        elif any(w in text_l for w in ["ближайш", "предстоящ", "скоро"]):
            upcoming = get_upcoming_phases(days=30)
            if not upcoming:
                return "Ближайших этапов нет."
            lines = []
            for u in upcoming:
                sd = u['start_date'].strftime('%d.%m.%Y') if hasattr(u['start_date'], 'strftime') else str(u['start_date'])
                ed = u['end_date'].strftime('%d.%m.%Y') if hasattr(u['end_date'], 'strftime') else str(u['end_date'])
                lines.append(f"• {u['phase_name']} — {sd}–{ed}")
            return "📅 Ближайшие этапы:\n" + "\n".join(lines)
        else:
            phases = get_schedule()
            lines = []
            status_icon = {"completed": "✅", "active": "🔄", "planned": "⏳"}
            for p in phases:
                pnum = p['phase_num']
                pname = p['phase_name']
                icon = status_icon.get(p['status'], '')
                sd = p['start_date'].strftime('%d.%m.%Y') if hasattr(p['start_date'], 'strftime') else str(p['start_date'])
                ed = p['end_date'].strftime('%d.%m.%Y') if hasattr(p['end_date'], 'strftime') else str(p['end_date'])
                if pnum is None:
                    # Milestone — indented sub-item
                    label = f"  ▸ {pname}"
                elif pname.startswith('Этап'):
                    label = f"• {pname}"
                else:
                    label = f"• Этап {pnum}: {pname}"
                lines.append(f"{label} — {sd}–{ed} {icon}")
            return "📅 График работ:\n" + "\n".join(lines)
    except Exception as e:
        print(f"[SCHEDULE ERR] {e}", flush=True)
        return None
