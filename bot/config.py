"""
config.py — Centralized configuration for Alikhan WhatsApp bot.
Single source of truth for all constants, URLs, paths, and simulation settings.

Usage:
    from config import SIM_DATE, SANDBOX, PRODUCTION, TEMPLATE_PATH, ...
"""
import os
from datetime import datetime

# ── Simulation date (set to None for production, or "2026-06-30" for testing) ──
SIM_DATE = None  # was "2026-06-30" — closed

# ── WhatsApp Groups ──
SANDBOX   = os.environ.get("WHATSAPP_SANDBOX", "")   # Testing group
PRODUCTION = os.environ.get("WHATSAPP_PRODUCTION", "")  # Production group

# ── API URLs ──
EVO_URL = "http://127.0.0.1:8080"
WAHA_URL = "http://127.0.0.1:3000"
XAI_URL = "https://api.x.ai/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WTTR_URL = "https://wttr.in/42.2,72.5?format=%C+%t+%w+%h+%P&lang=ru"

# ── Instance ──
EVO_INSTANCE = "alikhan"

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "ЕЖО_шаблон.xlsx")
SEEN_FILE = os.path.join(BASE_DIR, "seen_ids.json")
LOG_FILE = os.path.join(BASE_DIR, "bot.log")
SECRETS_FILE = os.path.expanduser("~/.hermes/secrets.env")
BACKUP_DIR = os.path.expanduser("/backups")
EJO_TMP_DIR = "/tmp"

# ── Time ──
BISHKEK_OFFSET_HOURS = 6  # UTC+6

# ── Poll ──
POLL_INTERVAL_SECONDS = 3
MAX_SEND_LENGTH = 3800

# ── Snapshot ──
SNAPSHOT_MAX_PHOTOS = 10
SNAPSHOT_MAX_MESSAGES = 30

# ── Completion percentage ──
PSD_WEIGHT_PCT = 6.0  # ПСД weight in completion calculation

# ── EJO ──
TEMPLATE_HEADER_ROWS = list(range(1, 24))  # rows 1-23 are headers
EJO_START_ROW = 24  # first data row in "Ежедневный отчет" sheet

# ── Voice triggers ──
VOICE_TRIGGERS = ["голосом", "озвучь", "голос"]

# ── Profession mapping (табель → шаблон) ──
PROF_MAP = {
    'рук.проекта': 'Руководителя строительства',
    'зам.рук.проекта': 'Руководителя строительства',
    'геодезист': 'Инженер геодезист',
    'тб': 'Инженер ТБ и ОТ',
    'пто': 'Инженер ПТО',
    'электрик': 'Электрик',
}

# ── Building profiles ──
BUILDINGS = ['АБК', 'Общежитие', 'Галерея']

# ── Helpers ──

def today_str():
    """Return today's date string, respecting SIM_DATE if set."""
    if SIM_DATE:
        return SIM_DATE
    return datetime.now().strftime("%Y-%m-%d")

def today_date():
    """Return today as date object, respecting SIM_DATE."""
    if SIM_DATE:
        return datetime.strptime(SIM_DATE, "%Y-%m-%d").date()
    return datetime.now().date()
