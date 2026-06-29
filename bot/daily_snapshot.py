#!/usr/bin/env python3
"""
Daily Snapshot Script for Alikhan bot
Runs at 8:00 and 16:00 MSK (6:00 and 14:00 UTC)
Generates structured report with weather + recent messages
"""

import os
import json
import psycopg2.extras
import requests
from datetime import datetime, timedelta
import urllib.request

from db import get_conn

# Load secrets
def _load_secrets():
    secrets = {}
    try:
        with open('/home/hermes-workspace/.hermes/secrets.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    secrets[k] = v
    except:
        pass
    return secrets

SECRETS = _load_secrets()
EVO_KEY = SECRETS.get('EVO_KEY', '')
EVO_DB_PASS = SECRETS.get('DB_PASS', 'pass123')

EVOLUTION_URL = "http://127.0.0.1:8080"
SANDBOX_GROUP = "120363179621030401@g.us"

def get_weather():
    """Get weather for ТЗРК Джеруй, Кыргызстан ~42.2, 72.5, alt 2700m"""
    try:
        url = "https://wttr.in/42.2,72.5?format=j1"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get('current_condition', [{}])[0]
            temp = current.get('temp_C', 'N/A')
            desc = current.get('lang_ru', [{}])[0].get('value', current.get('weatherDesc', [{}])[0].get('value', ''))
            wind = current.get('windspeedKmph', 'N/A')
            humidity = current.get('humidity', 'N/A')
            pressure_hpa = float(current.get('pressure', 0))
            pressure_mmhg = round(pressure_hpa * 0.75006)
            emoji = "🌤"
            desc = desc.strip()
            # Translate English conditions to Russian
            trans = {"Clear": "Ясно", "Sunny": "Солнечно", "Partly cloudy": "Переменная облачность",
                     "Cloudy": "Облачно", "Overcast": "Пасмурно", "Mist": "Туман", "Fog": "Туман",
                     "Light rain": "Небольшой дождь", "Rain": "Дождь", "Snow": "Снег"}
            for en, ru in trans.items():
                if desc.lower().startswith(en.lower()):
                    desc = ru + desc[len(en):]
                    break
            return f"{emoji} ТЗРК Джеруй (2700м): {desc}, +{temp}°C, ветер {wind}м/с, влажность {humidity}%, {pressure_mmhg} мм рт.ст."
    except Exception as e:
        pass
    return "🌤 ТЗРК Джеруй (2700м): данные недоступны"

def get_recent_messages(hours=8):
    """Query DB for ALL messages from last 8 hours"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    since = datetime.utcnow() - timedelta(hours=hours)
    cur.execute("""
        SELECT message_type, content, file_name, sender, COALESCE(message_time, created_at) as ts
        FROM bot_memory_messages
        WHERE COALESCE(message_time, created_at) >= %s
        ORDER BY COALESCE(message_time, created_at) DESC
        LIMIT 100
    """, (since,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_schedule_facts():
    """Get schedule/plan facts from bot_memory_facts"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT building, fact FROM bot_memory_facts WHERE category='документация' AND (fact LIKE '%График%' OR fact LIKE '%Этап%' OR fact LIKE '%дней%') ORDER BY id DESC LIMIT 15")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [f"[{r['building']}] {r['fact']}" for r in rows]
    except:
        return []

def generate_report(messages, weather, schedule):
    """Call Grok to generate structured daily report"""
    docs = [m for m in messages if m['message_type'] == 'document']
    photos = [m for m in messages if m['message_type'] == 'image']
    texts = [m for m in messages if m['message_type'] == 'text']
    
    today = datetime.now().strftime("%d %B %Y")
    today = today.replace("June", "июня").replace("July", "июля")
    
    # Deduplicate docs by filename
    seen_files = set()
    doc_list = []
    for d in docs:
        fn = d.get('file_name', 'без имени')
        if fn not in seen_files:
            seen_files.add(fn)
            content = (d.get('content', '') or '')[:2000]
            doc_list.append(f"{fn}: {content}")
    
    # Photo overview
    photo_list = [p.get('content', '')[:300] for p in photos[:10]]
    
    # Text messages  
    text_list = [t.get('content', '')[:200] for t in texts[:20]]
    
    prompt = f"""Сформируй ежедневный отчёт по проекту на русском языке:

📊 Снимок дня — {today}

Погода:
{weather}

График производства работ (план):
{chr(10).join(f'- {f}' for f in schedule) if schedule else '- не загружен'}

Документы (с кратким содержанием):
{chr(10).join(f'- {d}' for d in doc_list) if doc_list else '- нет'}

Фото:
{chr(10).join(f'- {p}' for p in photo_list) if photo_list else '- нет'}

Сообщения:
{chr(10).join(f'- {t}' for t in text_list) if text_list else '- нет'}

На основе этих данных составь отчёт строго по структуре:
1) Погода — как есть
- Документы — для каждого: от кого, кому, суть (допуск/вывоз/счёт/другое). 1 предложение. Запрещено: «письмо по ТЗРК» без конкретики.
3) Фото — общая картина как прораб: что делают, какая техника, ДВА здания:
   - АБК (Административно-бытовой корпус) — 2 этажа
   - Общежитие — 3 этажа
   Для каждого: что смонтировано, что залито, визуальная готовность
   Термины: бетонирование (не «бетонизация»), арматурный каркас (не «бетонирование металлокаркаса»), опалубка, перекрытие, стены, колонны
4) Сообщения — общая картина: что обсуждали в группе (не цитируй, дай обзор тем)
5) График — какие работы по плану на сегодня/завтра из загруженного графика производства работ
6) Выводы — только на основе данных выше. Сравни план (график) с фактом (фото/сообщения). Проблемы, риски, что требует внимания. Не выдумывай несуществующие отклонения от графика."""
    try:
        from handlers import ask_grok
        return ask_grok(prompt, max_tokens=1200)
    except:
        return prompt

def send_to_sandbox(text):
    """Send via Evolution API"""
    body = json.dumps({"number": SANDBOX_GROUP, "text": text[:3800]}).encode()
    req = urllib.request.Request(f'{EVOLUTION_URL}/message/sendText/alikhan', data=body, method='POST')
    req.add_header('apikey', EVO_KEY)
    req.add_header('Content-Type', 'application/json')
    try:
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:
        print("Send error:", e)

def main():
    print("Daily snapshot started at", datetime.now())
    weather = get_weather()
    messages = get_recent_messages(8)
    schedule = get_schedule_facts()
    report = generate_report(messages, weather, schedule)
    send_to_sandbox(report)
    print("Report sent to sandbox")

if __name__ == "__main__":
    main()
