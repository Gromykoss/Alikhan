#!/usr/bin/env python3
"""
Диспетчер WhatsApp-команд для Alikhan v2.
Слушает песочницу + боевую группу.
ВСЕ сообщения логируются.
Ролевая модель: admin > operator > viewer.
"""
import sys, os, json, time, requests, re, base64, traceback
from datetime import datetime, timezone, timedelta

BISHKEK_TZ = timezone(timedelta(hours=6))


def bishkek_date_str():
    return datetime.now(BISHKEK_TZ).strftime("%Y-%m-%d")


def bishkek_date():
    return datetime.now(BISHKEK_TZ).date()


BRIDGE = "http://127.0.0.1:3000"
SANDBOX = "120363179621030401@g.us"
PRODUCTION = "120363400682390076@g.us"
SEEN_FILE = "/tmp/alikhan_seen.json"
LOG_FILE = "/tmp/alikhan_commands.log"

# --- Ролевая модель ---
ROLE_HIERARCHY = {"admin": 3, "operator": 2, "viewer": 1}


def _load_roles() -> dict:
    """Загрузить роли из authorised_senders.json. Обратная совместимость со старым форматом."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "authorized_senders.json"),
        "/home/hermes-workspace/Alikhan-migration/bot/authorized_senders.json",
    ]
    for path in candidates:
        try:
            with open(path) as f:
                data = json.load(f)
            if "roles" in data:
                return data.get("roles", {})
            elif "authorized_senders" in data:
                # Старый формат — все становятся admin
                return {phone: "admin" for phone in data.get("authorized_senders", [])}
        except Exception:
            continue
    return {}


ROLES = _load_roles()


def _save_roles() -> bool:
    """Сохранить роли на диск (канонический путь — bot/authorized_senders.json)."""
    try:
        path = "/home/hermes-workspace/Alikhan-migration/bot/authorized_senders.json"
        with open(path, "w") as f:
            json.dump({"roles": ROLES}, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log(f"SAVE_ROLES ERR: {e}")
        return False


# Путь к bot/ для импортов
BOT_DIR = "/home/hermes-workspace/Alikhan-migration/bot"
sys.path.insert(0, BOT_DIR)


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def get_sender(msg: dict) -> str:
    """Извлечь номер отправителя из сообщения Bridge."""
    sender = msg.get("senderId") or msg.get("author") or msg.get("from") or ""
    return re.sub(r"\D", "", sender)


def get_role(msg: dict) -> str | None:
    """Получить роль отправителя. None — не авторизован."""
    return ROLES.get(get_sender(msg))


def check_role(msg: dict, min_role: str) -> bool:
    """Проверить, что у отправителя роль не ниже min_role (admin > operator > viewer)."""
    role = get_role(msg)
    if role is None:
        return False
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(min_role, 99)


def _deny_role(msg: dict, chat_id: str, required_role: str) -> bool:
    """Отказать в доступе из-за недостаточной роли. viewer — молча."""
    role = get_role(msg)
    log(f"CMD DENIED: insufficient role (has {role}, need {required_role})")
    if role == "viewer":
        # viewer — silently ignored, no response
        return True
    send_message(chat_id, f"⛔ Недостаточно прав. Требуется роль: {required_role}")
    return True


def load_seen() -> set:
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(ids: set):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(ids), f)
    except Exception as e:
        log(f"SAVE_SEEN ERR: {e}")

def send_collect_ack(ids: list) -> bool:
    """Подтвердить мосту успешную обработку батча (durability, аудит).

    POST {BRIDGE}/collect-ack {"ids": [...]} — мост удаляет эти id из своего
    файлового журнала. Не-ack id восстанавливаются после рестарта моста
    (re-drain в collectQueue) → диспетчер ретраит их следующим тиком.
    Вызывается ТОЛЬКО с успешно обработанными id (confirmed[]); упавшие
    БД-записи в список не попадают."""
    if not ids:
        return True
    try:
        resp = requests.post(f"{BRIDGE}/collect-ack", json={"ids": ids}, timeout=5)
        ok = resp.status_code == 200
        log(f"ACK {len(ids)} ids → /collect-ack: {'OK' if ok else f'HTTP {resp.status_code}'}")
        return ok
    except Exception as e:
        log(f"ACK ERR: {e} — ids останутся в журнале моста (re-drain после рестарта)")
        return False

def get_messages() -> list:
    # v4: ТОЛЬКО /collect-messages. /messages?only=<collect-only-JID> на новом
    # мосту ОПАСЕН: collect-only JID вырезаются из only= → список пустеет →
    # legacy splice всей очереди шлюза (кража песочницы). Поэтому fallback на
    # /messages ЗАПРЕЩЁН: при health fail или отсутствии collectOnlyChats
    # возвращаем [] — следующий тик крона повторит попытку.
    try:
        health = requests.get(f"{BRIDGE}/health", timeout=3).json()
    except Exception as e:
        log(f"BRIDGE HEALTH ERR: {e} — collect-only не подтверждён, тик пропущен")
        return []
    if not health.get("collectOnlyChats"):
        # Старый мост / новый без конфига / health не отдал ключ:
        # НЕ читаем /messages, возвращаем пусто.
        log("BRIDGE: collectOnlyChats отсутствует — /messages НЕ читаю, тик пропущен")
        return []
    try:
        resp = requests.get(f"{BRIDGE}/collect-messages?only={PRODUCTION}", timeout=5)
        if resp.status_code != 200:
            log(f"BRIDGE HTTP {resp.status_code} (/collect-messages)")
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log(f"BRIDGE ERR: {e}")
        return []


def send_message(chat_id: str, text: str) -> bool:
    if chat_id == PRODUCTION:
        # ⛔ Client-side collect-only guard: боевая группа listen-only.
        # НИКОГДА не отправляем, даже если мост не вернёт 403.
        log(f"SEND BLOCKED: PRODUCTION listen-only (client guard), text '{text[:40]}' skipped")
        return False
    try:
        resp = requests.post(f"{BRIDGE}/send", json={
            "chatId": chat_id, "message": text
        }, timeout=10)
        ok = resp.status_code == 200 and resp.json().get("success", False)
        log(f"SEND [{chat_id[-12:]}]: {'OK' if ok else 'FAIL'}")
        return ok
    except Exception as e:
        log(f"SEND ERR: {e}")
        return False


def send_file(chat_id: str, filepath: str, filename: str = None) -> bool:
    if chat_id == PRODUCTION:
        # ⛔ Client-side collect-only guard: боевая группа listen-only.
        log(f"SEND_FILE BLOCKED: PRODUCTION listen-only (client guard), {filename or os.path.basename(filepath)} skipped")
        return False
    try:
        fname = filename or os.path.basename(filepath)
        with open(filepath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        resp = requests.post(f"{BRIDGE}/send", json={
            "chatId": chat_id, "fileName": fname, "fileData": b64,
            "caption": fname
        }, timeout=30)
        ok = resp.status_code == 200 and resp.json().get("success", False)
        log(f"SEND_FILE [{chat_id[-12:]}]: {fname} {'OK' if ok else 'FAIL'}")
        return ok
    except Exception as e:
        log(f"SEND_FILE ERR: {e}")
        return False


def handle_sandbox_command(text: str, chat_id: str, msg: dict | None = None):
    """Команды — только из песочницы. Ролевая модель доступа."""
    # ⛔ Access control gate — completely unauthorized (not in ROLES at all)
    if msg is not None and get_role(msg) is None:
        log(f"CMD DENIED: unauthorized sender")
        send_message(chat_id, "⛔ Команды принимаю только от руководителя.")
        return True

    t = text.lower().strip()
    log(f"CMD? '{t[:80]}'")

    # ═══════════════════════════════════════════
    # Admin-only: управление ролями
    # ═══════════════════════════════════════════

    if "алихан" in t and ("добавь оператора" in t or "добавить оператора" in t):
        if msg is not None and not check_role(msg, "admin"):
            return _deny_role(msg, chat_id, "admin")
        log("CMD: add_operator")
        nums = re.findall(r'\d{10,12}', t)
        if nums:
            phone = nums[0]
            ROLES[phone] = "operator"
            if _save_roles():
                send_message(chat_id, f"✅ Оператор {phone} добавлен")
            else:
                send_message(chat_id, "❌ Ошибка сохранения ролей")
        else:
            send_message(chat_id, "❌ Укажите номер: алихан добавь оператора 7995...")
        return True

    if "алихан" in t and ("убери оператора" in t or "убрать оператора" in t):
        if msg is not None and not check_role(msg, "admin"):
            return _deny_role(msg, chat_id, "admin")
        log("CMD: remove_operator")
        nums = re.findall(r'\d{10,12}', t)
        if nums:
            phone = nums[0]
            if phone in ROLES:
                removed_role = ROLES.pop(phone)
                if _save_roles():
                    send_message(chat_id, f"✅ {phone} удалён (был {removed_role})")
                else:
                    send_message(chat_id, "❌ Ошибка сохранения ролей")
            else:
                send_message(chat_id, f"❌ Номер {phone} не найден в доступе")
        else:
            send_message(chat_id, "❌ Укажите номер: алихан убери оператора 7995...")
        return True

    if "алихан" in t and "кто в доступе" in t:
        if msg is not None and not check_role(msg, "admin"):
            return _deny_role(msg, chat_id, "admin")
        log("CMD: list_roles")
        if not ROLES:
            send_message(chat_id, "📋 Доступ пуст — никто не добавлен.")
        else:
            lines = ["📋 *Доступ:*"]
            for phone, role in sorted(ROLES.items()):
                emoji = {"admin": "👑", "operator": "🔧", "viewer": "👁"}.get(role, "❓")
                lines.append(f"{emoji} {phone} — {role}")
            send_message(chat_id, "\n".join(lines))
        return True

    # ═══════════════════════════════════════════
    # Operator+: продуктовый функционал
    # ═══════════════════════════════════════════

    # --- ЕЖО ---
    if "алихан" in t and ("заполни ежо" in t or "ежо принудительно" in t
                          or "формируй ежо" in t or "формируй отчет" in t):
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")
        force = "принудительно" in t or "все равно" in t or "несмотря" in t
        log(f"CMD: fill_ejo force={force}")

        import subprocess
        today = bishkek_date_str()
        venv = "/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3"

        result = subprocess.run(
            [venv, "fill_ejo.py", today] + (["--force"] if force else []),
            cwd=BOT_DIR, capture_output=True, text=True, timeout=120
        )
        log(f"fill_ejo rc={result.returncode}")

        import glob as g
        files = sorted(
            g.glob(f"/tmp/ЕЖО_{today.replace('-', '.')}*.xlsx") +
            g.glob(f"/tmp/ЕЖО_{today}*.xlsx"),
            key=os.path.getmtime, reverse=True
        )

        if files:
            if send_file(chat_id, files[0]):
                send_message(chat_id, f"📊 ЕЖО за {today} отправлен")
        else:
            send_message(chat_id, "❌ Не удалось сформировать ЕЖО")
        return True

    # --- Раскрыть отчёт ---
    if "алихан" in t and "раскрой отчет" in t:
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")
        log("CMD: раскрыть отчет")
        import subprocess
        venv = "/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3"
        subprocess.run(
            [venv, "-c", f"""
import sys; sys.path.insert(0, '{BOT_DIR}')
import main_waha as m
m.SANDBOX = "{SANDBOX}"
m._expand_template(m.SANDBOX)
"""], capture_output=True, text=True, timeout=60)
        return True

    # --- Опрос ---
    if "алихан" in t and ("запускай опрос" in t or "запусти опрос" in t):
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")
        log("CMD: start poll")
        try:
            from poll import start_poll
            start_poll(chat_id)
        except Exception as e:
            log(f"POLL START ERR: {e}")
            send_message(chat_id, f"❌ Ошибка: {e}")
        return True

    if "алихан" in t and "статус опроса" in t:
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")
        log("CMD: poll status")
        try:
            from poll import get_poll_status
            send_message(chat_id, get_poll_status())
        except Exception as e:
            log(f"POLL STATUS ERR: {e}")
        return True

    if "алихан" in t and ("закончить опрос" in t or "закрой опрос" in t):
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")
        log("CMD: close poll")
        try:
            from poll import close_poll
            close_poll(chat_id)
        except Exception as e:
            log(f"POLL CLOSE ERR: {e}")
        return True

    # --- АВР (КС-2 и КС-6) ---
    # Три режима: весь период, конкретный месяц, текущий месяц
    _avr_triggers = (
        "алихан авр" in t or "формируй авр" in t or "сформируй авр" in t
        or re.search(r"(?:^|\s)авр(?:\s|$)", t)
        or re.search(r"(?:^|\s)кс[\s-]?[26](?:\s|$)", t)
    )
    if _avr_triggers:
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")

        log("CMD: avr")
        send_message(chat_id, "📑 Формирую КС-2 и КС-6...")

        import calendar
        from datetime import date
        from avr import format_summary, generate_ks2, generate_ks6
        from db import get_conn

        report_day = bishkek_date()
        year = report_day.year

        if "весь период" in t:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT MIN(work_date) FROM ojr_section3_work_log")
            period_start = cur.fetchone()[0]
            conn.close()
            period_end = report_day
        else:
            # Попытка распарсить месяц из текста
            _ru_months = {
                "январь": 1, "января": 1, "февраль": 2, "февраля": 2,
                "март": 3, "марта": 3, "апрель": 4, "апреля": 4,
                "май": 5, "мая": 5, "июнь": 6, "июня": 6,
                "июль": 7, "июля": 7, "август": 8, "августа": 8,
                "сентябрь": 9, "сентября": 9, "октябрь": 10, "октября": 10,
                "ноябрь": 11, "ноября": 11, "декабрь": 12, "декабря": 12,
            }
            m = re.search(r"(?:авр(?:\s+за)?\s+)([а-я]+)", t)
            month_num = None
            if m:
                token = m.group(1)
                candidates = {_ru_months[name] for name in _ru_months if name.startswith(token) and len(token) >= 3}
                if len(candidates) == 1:
                    month_num = candidates.pop()

            if month_num:
                period_start = report_day.replace(month=month_num, day=1)
                period_end = period_start.replace(day=calendar.monthrange(year, month_num)[1])
            else:
                period_start = report_day.replace(day=1)
                period_end = report_day.replace(day=calendar.monthrange(year, report_day.month)[1])

        try:
            ks2_path, ks2_summary = generate_ks2(period_start, period_end)
            ks6_path, _ = generate_ks6(period_end)
            send_message(chat_id, f"✅ АВР сформирован\n{format_summary(ks2_summary)}")
            send_file(chat_id, ks2_path)
            send_file(chat_id, ks6_path)
        except Exception as e:
            log(f"AVR ERR: {e}")
            send_message(chat_id, f"❌ Ошибка формирования АВР: {e}")
        return True

    # --- Снимок дня ---
    if "алихан" in t and (
        "снимок дня" in t or "daily snapshot" in t
        or re.search(r"(?:^|\s)snapshot(?:$|\s)", t)
        or "снимок" in t
    ):
        if msg is not None and not check_role(msg, "operator"):
            return _deny_role(msg, chat_id, "operator")
        log("CMD: daily_snapshot")
        send_message(chat_id, "📸 Формирую снимок дня...")
        try:
            from main_waha import generate_daily_snapshot
            snap_text = generate_daily_snapshot(chat_id)
            send_message(chat_id, snap_text)
        except Exception as e:
            log(f"SNAPSHOT ERR: {e}")
            send_message(chat_id, f"❌ Ошибка формирования снимка: {e}")
        return True

    return False


def extract_text(msg: dict) -> str:
    if msg.get("body"):
        return msg["body"]
    if msg.get("conversation"):
        return msg["conversation"]
    if msg.get("extendedTextMessage", {}).get("text"):
        return msg["extendedTextMessage"]["text"]
    if msg.get("message"):
        return str(msg["message"])
    if msg.get("imageMessage", {}).get("caption"):
        return msg["imageMessage"]["caption"]
    if msg.get("documentMessage", {}).get("caption"):
        return msg["documentMessage"]["caption"]
    return ""


def is_qa_text(text: str) -> bool:
    t = text.lower()
    triggers = ["майкадам", "атантай", "наватек", "айбикон",
                "рабочие", "рабочих", "итр", "поставки",
                "техника", "материал", "происшестви",
                "=", "м3", "м2", "кг", " т ", "шт"]
    return any(w in t for w in triggers)


def handle_qa(text: str, chat_id: str):
    log(f"QA [{chat_id[-12:]}]: '{text[:80]}'")
    try:
        from qa import parse_qa
        today = bishkek_date_str()
        # ВАЖНО: parse_qa(gid, text, date_str) — gid ПЕРВЫМ аргументом.
        # Раньше было parse_qa(text, chat_id, today) — gid=текст, text=chat_id.
        facts = parse_qa(chat_id, text, today)
        if facts and chat_id == SANDBOX:
            send_message(chat_id, f"✅ Принято: {len(facts)} фактов")
        elif facts:
            log(f"QA: {len(facts)} facts (prod, silent)")
    except Exception as e:
        log(f"QA ERR: {e}\n{traceback.format_exc()}")
        if chat_id == SANDBOX:
            send_message(chat_id, f"❌ Ошибка: {e}")


# ─── Сбор данных из боевой группы (listen-only, v3 — 2026-08-01) ───────────
# Боевая группа 120363400682390076@g.us: ТОЛЬКО сбор (фото/документы/тексты →
# bot_memory_messages + ojr_photo_log + ojr_* через parse_qa). Ответов в боевую
# НИКОГДА не отправляем — только лог. Песочницу целиком обслуживает Hermes-шлюз.

PHOTO_BUILDINGS = ["АБК", "Общежитие", "Галерея", "Общий план"]


def _media_local_path(msg: dict):
    """Локальный путь скачанного мостом медиа (поле mediaUrls — кэш-файлы)."""
    urls = msg.get("mediaUrls") or []
    if isinstance(urls, str):
        urls = [urls]
    urls = [u for u in urls if u]
    for u in urls:
        if os.path.exists(u):
            return u
    return urls[0] if urls else None


def _detect_building(caption: str):
    c = (caption or "").lower()
    for tag in PHOTO_BUILDINGS:
        if tag.lower() in c:
            return tag
    return None


# ─── Классификация фото без caption-здания (vision, 2026-08-02) ────────────
# Поздравительные открытки (День строителя и т.п.) из боевой НЕ должны
# попадать в ojr_photo_log (журнал строительных фото для ЕЖО) как «Общий план».
VISION_UNAVAILABLE_BUILDING = "Фото (описание недоступно)"
GREETING_CARD_BUILDING = "Поздравительная открытка"
CONSTRUCTION_DEFAULT_BUILDING = "Строительная площадка"
SITE_RELATED_DEFAULT_BUILDING = "Связано с объектом (не стройка)"
UNRELATED_DEFAULT_BUILDING = "Постороннее фото"
GREETING_KEYWORDS = (
    "поздрав", "открытк", "день строителя", "днём строителя", "днем строителя",
    "с праздником", "congratul",
)

# 3-категорийная классификация фото (2026-08-02):
#   construction — стройка → ojr_photo_log;
#   site_related — связано с объектом, но НЕ стройка (материалы, техника, бытовки,
#                  инфраструктура) → только bot_memory_messages с тегом category;
#   unrelated    — постороннее (открытки, поздравления, личные фото, мемы) →
#                  только bot_memory_messages с тегом category.
CATEGORY_CONSTRUCTION = "construction"
CATEGORY_SITE_RELATED = "site_related"
CATEGORY_UNRELATED = "unrelated"
PHOTO_CATEGORIES = (CATEGORY_CONSTRUCTION, CATEGORY_SITE_RELATED, CATEGORY_UNRELATED)


def _detect_greeting(caption: str) -> bool:
    """Открытка/поздравление по caption (дешевле vision и надёжнее для
    типового случая «С Днём строителя!»)."""
    c = (caption or "").lower()
    return any(k in c for k in GREETING_KEYWORDS)


def _normalize_vision_area(value):
    """Привести area_identified из Grok vision к каноническому имени здания
    (АБК/Общежитие/Галерея/Общий план) либо вернуть сырое значение."""
    v = (value or "").strip()
    if not v:
        return None
    vl = v.lower()
    for tag in PHOTO_BUILDINGS:
        if tag.lower() in vl:
            return tag
    return v[:80]


def _classify_photo_via_vision(local_path: str, mimetype: str = "image/jpeg"):
    """Grok vision: 3-категорийная классификация фото БЕЗ caption-здания.

    Использует vision_checklist.checklist_from_image (расширенный CHECKLIST_PROMPT
    с полем category — промпты не дублируются). Категории:
      construction — стройка: строительные работы/прогресс на объекте;
      site_related — связано с объектом, но НЕ стройка: материалы, техника,
                     бытовки, инфраструктура, транспорт объекта;
      unrelated    — постороннее: открытки, поздравления, личные фото, мемы.

    Если vision не вернул явную category — fallback по сигналам чеклиста:
    area/рабочие/прогресс/безопасность → construction; только техника →
    site_related; ничего → unrelated (weather_visible НЕ сигнал — у открытки
    с небом-иллюстрацией он может быть observed).

    Возвращает (building, classification, category, cat_description):
      construction       → (здание из area_identified | «Строительная площадка»,
                            "construction", "construction", None)
      site_related       → (здание | «Связано с объектом (не стройка)»,
                            "site_related", "site_related", описание категории)
      unrelated          → («Поздравительная открытка» | «Постороннее фото»,
                            "unrelated", "unrelated", описание категории)
      vision_unavailable → («Фото (описание недоступно)», "vision_unavailable",
                            None, None)
    """
    try:
        from vision_checklist import checklist_from_image
        with open(local_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        checklist = checklist_from_image(image_base64, mimetype)
    except Exception as e:
        log(f"[PRD] PHOTO VISION ERR: {e}")
        return VISION_UNAVAILABLE_BUILDING, "vision_unavailable", None, None

    if not checklist or "_error" in checklist:
        err = checklist.get("_error") if isinstance(checklist, dict) else "?"
        log(f"[PRD] PHOTO VISION unavailable (checklist _error={err})")
        return VISION_UNAVAILABLE_BUILDING, "vision_unavailable", None, None

    from vision_checklist import checklist_category
    category, reason = checklist_category(checklist)

    area = checklist.get("area_identified") or {}
    area_value = str(area.get("value") or "").strip()
    area_ok = bool(area.get("observed")) and bool(area_value)
    building = _normalize_vision_area(area_value) if area_ok else None

    signals = []
    for f in ("workers_count", "equipment_visible", "progress_vs_plan", "safety_issues"):
        e = checklist.get(f) or {}
        if e.get("observed") and str(e.get("value") or "").strip():
            signals.append(f)

    # 1. construction: явная категория vision ИЛИ fallback-сигналы стройки
    if category == CATEGORY_CONSTRUCTION or (
            not category and (area_ok or any(s in signals for s in
                                             ("workers_count", "progress_vs_plan", "safety_issues")))):
        building = building or CONSTRUCTION_DEFAULT_BUILDING
        log(f"[PRD] PHOTO VISION category=construction (signals: {', '.join(signals) or 'area'}) → building={building}")
        return building, CATEGORY_CONSTRUCTION, CATEGORY_CONSTRUCTION, None

    # 2. site_related: явная категория vision ИЛИ только техника/оборудование
    if category == CATEGORY_SITE_RELATED or (not category and "equipment_visible" in signals):
        building = building or SITE_RELATED_DEFAULT_BUILDING
        desc = reason or "Связано с объектом (не стройка)"
        log(f"[PRD] PHOTO VISION category=site_related (не стройка: {desc}) → building={building}")
        return building, CATEGORY_SITE_RELATED, CATEGORY_SITE_RELATED, desc

    # 3. unrelated: явная категория vision ИЛИ отсутствие любых сигналов стройки
    if reason and _detect_greeting(reason):
        building = GREETING_CARD_BUILDING
    else:
        building = UNRELATED_DEFAULT_BUILDING
    desc = reason or "Постороннее фото (сигналы стройки отсутствуют)"
    log(f"[PRD] PHOTO VISION category=unrelated ({desc}) → building={building}")
    return building, CATEGORY_UNRELATED, CATEGORY_UNRELATED, desc


def _clean_body(msg: dict) -> str:
    """body моста для медиа = caption. Плейсхолдеры вида '[image received]' — пусто."""
    body = (msg.get("body") or "").strip()
    if body.startswith("[") and body.endswith("received]"):
        return ""
    return body


def _insert_media_message(chat_id, sender, message_type, mid, tags):
    """bot_memory_messages: content=mid (дедуп), tags=jsonb. Возвращает id."""
    conn = None
    try:
        from db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM bot_memory_messages WHERE chat_id=%s AND content=%s AND message_type=%s LIMIT 1",
            (chat_id, mid, message_type))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at) "
            "VALUES (%s, %s, 'user', %s, %s, %s, %s) RETURNING id",
            (chat_id, sender, message_type, mid,
             json.dumps(tags, ensure_ascii=False), datetime.now(BISHKEK_TZ)))
        rid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return rid
    except Exception as e:
        log(f"MEDIA INSERT ERR: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _save_prod_photo(msg, mid) -> bool:
    """Фото из боевой: bot_memory_messages (метаданные ВСЕГДА) + ojr_photo_log.
    Кэш-файла нет ИЛИ mediaMissing:true → строка с file_path=NULL (факт прихода
    фото не теряется; бинарь недоступен — факт прихода сохранён метаданными).
    Классификация (3 категории, 2026-08-02; порядок уточнён 2026-08-02 по
    замечанию Codex — greeting по caption идёт ПЕРВЫМ):
      - caption-поздравление (_detect_greeting) → category=unrelated,
        «Поздравительная открытка», НЕ в ojr_photo_log — даже если в caption есть
        здание («АБК поздравляет с Днём строителя» — открытка, а НЕ стройка);
      - нет caption-поздравления → Grok vision (vision_checklist.checklist_from_image,
        поле category): construction → building из area_identified (или «Строительная
        площадка»), в ojr_photo_log; site_related → «Связано с объектом (не стройка)»
        + описание категории, НЕ в ojr_photo_log; unrelated → «Поздравительная
        открытка»/«Постороннее фото», НЕ в ojr_photo_log;
      - vision недоступна (файла нет) → caption-здание (АБК/Общежитие/Галерея/
        Общий план) → как раньше, в ojr_photo_log;
      - ни поздравления, ни здания, ни vision → «Фото (описание недоступно)»,
        НЕ в ojr_photo_log
        (только bot_memory_messages с тегом classification=vision_unavailable).
    Все не-строительные фото сохраняются в bot_memory_messages с тегом category
    (site_related/unrelated) и описанием category_description.
    Возвращает True, только если факт фото зафиксирован в БД полностью."""
    cap = _clean_body(msg)
    media_missing = bool(msg.get("mediaMissing"))
    local_path = None if media_missing else _media_local_path(msg)
    mimetype = msg.get("mime") or "image/jpeg"

    # Порядок проверок (2026-08-02, замечание Codex): greeting по caption — ПЕРВЫМ,
    # иначе caption «АБК поздравляет с Днём строителя» перехватится _detect_building
    # («АБК») как стройка. Затем vision-классификация (caption не поздравление и
    # файл есть), и только потом caption-здание — fallback, когда vision недоступна
    # (файла нет).
    if _detect_greeting(cap):
        building = GREETING_CARD_BUILDING
        classification = "greeting_card"
        category = CATEGORY_UNRELATED
        cat_description = "Поздравительная открытка"
    elif local_path:
        building, classification, category, cat_description = _classify_photo_via_vision(local_path, mimetype)
    elif (caption_building := _detect_building(cap)):
        building = caption_building
        classification = "caption"
        category = CATEGORY_CONSTRUCTION
        cat_description = None
    else:
        building = VISION_UNAVAILABLE_BUILDING
        classification = "vision_unavailable"
        category = None
        cat_description = None

    sender = msg.get("senderId") or msg.get("senderNumber") or "user"
    tags = {"msg_id": mid, "building": building}
    if classification != "caption":
        tags["classification"] = classification
    if category:
        tags["category"] = category
    if cat_description:
        tags["category_description"] = cat_description
    if media_missing:
        tags["media_missing"] = True
    if local_path:
        tags["local_path"] = local_path
    rid = _insert_media_message(PRODUCTION, sender, "image", mid, tags)
    if rid is None:
        log(f"[PRD] PHOTO {mid[:12]} DB FAIL (metadata row not saved) — seen NOT marked")
        return False
    if media_missing:
        log(f"[PRD] PHOTO {mid[:12]} MEDIA MISSING (download failed) — metadata row {rid}, file_path=NULL, ACK'ed (факт прихода сохранён)")
    elif not local_path:
        log(f"[PRD] PHOTO {mid[:12]} no local file (mediaUrls={msg.get('mediaUrls')}) — metadata row {rid}, file missing")
    # В ojr_photo_log — ТОЛЬКО строительные фото (caption-здание или vision-construction).
    # site_related / unrelated / greeting_card / vision_unavailable — не стройка.
    if classification not in ("caption", CATEGORY_CONSTRUCTION):
        log(f"[PRD] PHOTO {mid[:12]} category={category or classification} (не стройка) — metadata row {rid}, ojr_photo_log SKIPPED (building={building})")
        return True
    conn = None
    try:
        from db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM ojr_title_page WHERE is_active = TRUE LIMIT 1")
        trow = cur.fetchone()
        title_id = trow[0] if trow else 1
        photo_date = datetime.now(BISHKEK_TZ).strftime("%Y-%m-%d")
        cur.execute("SELECT 1 FROM ojr_photo_log WHERE file_message_id=%s LIMIT 1", (rid,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO ojr_photo_log (title_id, photo_date, building, file_message_id, file_path, file_name, mime_type, caption, created_at) "
                "VALUES (%s, %s::date, %s, %s, %s, %s, %s, %s, NOW())",
                (title_id, photo_date, building, rid, local_path,
                 os.path.basename(local_path) if local_path else None,
                 msg.get("mime") or "image/jpeg", cap or None))
            conn.commit()
            if local_path:
                log(f"[PRD] PHOTO saved: {building} — {os.path.basename(local_path)} (row {rid})")
            else:
                log(f"[PRD] PHOTO metadata-only: {building} (row {rid}, файл недоступен)")
        else:
            log(f"[PRD] PHOTO already logged (msg {mid[:12]})")
        cur.close()
        return True
    except Exception as e:
        log(f"PHOTO OJR ERR: {e} — seen NOT marked, retry next tick")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ─── OCR текста документов из боевой (T-174, 2026-08-02) ────────────────────
# После сохранения документа (bot_memory_messages, row уже есть) — best-effort
# POST /extract-document (path) → extracted_text/extract_ok/extract_error в tags.
# Любые ошибки (сервис недоступен/таймаут 5с/БД) НЕ ломают обработку: документ
# сохранён как раньше, ack/seen не меняются — только теги помечаются.
DOC_OCR_EXTS = {".pdf", ".xlsx", ".xls", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"}
EXTRACTOR_URL = "http://127.0.0.1:8099/extract-document"


def _ocr_document_tags(rid, local_path):
    """OCR текста документа по local_path → дописать теги в bot_memory_messages.
    Теги: extract_ok ('true'/'false'), extracted_text (если есть), extract_error
    (если не ok). Логи [PRD] DOC OCR ok/fail. Исключения не пробрасываются."""
    extra = {}
    try:
        resp = requests.post(EXTRACTOR_URL, json={"path": local_path}, timeout=5)
        data = resp.json()
        ok = bool(data.get("ok"))
        text = str(data.get("text") or "").strip()
        extra["extract_ok"] = "true" if ok else "false"
        if text:
            # В теги кладём не более 20000 символов (защита от раздувания БД);
            # в логи содержимое документа НЕ выводится.
            extra["extracted_text"] = text[:20000]
        if not ok:
            err = str(data.get("error") or f"HTTP {resp.status_code}")
            extra["extract_error"] = err[:500]
        if ok:
            log(f"[PRD] DOC OCR ok (len={len(text)})")
        else:
            log(f"[PRD] DOC OCR FAIL: {extra.get('extract_error')}")
    except Exception as e:
        extra["extract_ok"] = "false"
        extra["extract_error"] = str(e)[:500]
        log(f"[PRD] DOC OCR FAIL: {e}")
    if not extra:
        return
    conn = None
    try:
        from db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE bot_memory_messages SET tags = tags || %s::jsonb WHERE id = %s",
            (json.dumps(extra, ensure_ascii=False), rid))
        conn.commit()
        cur.close()
        log(f"[PRD] DOC OCR tags → row {rid}: {list(extra)}")
    except Exception as e:
        log(f"[PRD] DOC OCR tags update ERR: {e} (row {rid})")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _save_prod_document(msg, mid) -> bool:
    """Документ из боевой: bot_memory_messages (метаданные ВСЕГДА, local_path — если кэш есть).
    mediaMissing:true → метаданные с file_path=NULL + лог MEDIA MISSING, ack'ается
    (факт прихода сохранён метаданными, бинарь недоступен).
    Возвращает True, только если строка записана в БД."""
    fname = msg.get("fileName") or "document"
    cap = _clean_body(msg)
    media_missing = bool(msg.get("mediaMissing"))
    local_path = None if media_missing else _media_local_path(msg)
    sender = msg.get("senderId") or msg.get("senderNumber") or "user"
    tags = {"msg_id": mid, "file_name": fname}
    if media_missing:
        tags["media_missing"] = True
    if local_path:
        tags["local_path"] = local_path
    rid = _insert_media_message(PRODUCTION, sender, "document", mid, tags)
    if rid is None:
        log(f"[PRD] DOC DB FAIL: {fname} ({mid[:12]}) — seen NOT marked")
        return False
    if media_missing:
        log(f"[PRD] DOC {mid[:12]} MEDIA MISSING (download failed): {fname} — metadata row {rid}, file_path=NULL, ACK'ed (факт прихода сохранён)")
    elif local_path:
        log(f"[PRD] DOC saved: {fname} → {local_path} (row {rid})")
    else:
        log(f"[PRD] DOC metadata-only: {fname} (row {rid}, mediaUrls={msg.get('mediaUrls')}, файл недоступен)")
    # OCR текста документа (T-174): только если файл есть и расширение поддерживается.
    # Best-effort — ошибки extractor'а/БД не влияют на ack/seen (документ уже сохранён).
    if local_path and os.path.splitext(local_path)[1].lower() in DOC_OCR_EXTS:
        _ocr_document_tags(rid, local_path)
    return True


def _save_prod_text(text, chat_id, mid, sender) -> bool:
    """Текст из боевой: всегда сырая запись + parse_qa → ojr_* (если QA). Silent.
    Возвращает True, только если сырая запись легла в БД (QA — best-effort)."""
    try:
        from db import save_message
        save_message(chat_id, sender, "user", text, message_type="text")
    except Exception as e:
        log(f"RAW TEXT ERR: {e} — seen NOT marked, retry next tick")
        return False
    if is_qa_text(text):
        handle_qa(text, chat_id)
    return True


def main():
    log("START")
    seen = load_seen()
    messages = get_messages()
    log(f"GOT {len(messages)} msgs, {len(seen)} seen")

    new_count = 0
    confirmed = []  # mid, подтверждённые обработкой → seen (durability: только после успеха)
    ack_ids = []    # mid → POST /collect-ack (успешно обработанные + re-ack seen из журнала моста)
    for msg in messages:
        mid = msg.get("messageId") or msg.get("id")
        if not mid:
            continue
        if mid in seen:
            # Пришёл повторно (re-drain файлового журнала после рестарта моста):
            # ack'аем повторно, чтобы мост удалил id из журнала, обработку не дублируем.
            ack_ids.append(mid)
            continue

        chat_id = msg.get("chatId", "")
        # Свои сообщения из ПЕСОЧНИЦЫ / не-боевых чатов: данных для записи нет —
        # помечаем seen без БД (иначе ретрай вечно). Данные при этом не теряются.
        # Песочница: fromMe/fromOwner пропускаем как и раньше (не меняем).
        if (msg.get("fromMe") or msg.get("fromOwner")) and chat_id != PRODUCTION:
            confirmed.append(mid)
            ack_ids.append(mid)
            continue
        # Диспетчер получает из очереди ТОЛЬКО боевую (/collect-messages?only=PRODUCTION).
        # Песочницу обслуживает Hermes-шлюз — сюда она не попадает.
        if chat_id != PRODUCTION:
            confirmed.append(mid)
            ack_ids.append(mid)
            continue
        # fromMe/fromOwner ИЗ БОЕВОЙ (120363400682390076@g.us): свои сообщения
        # несут данные (отчёты, фото, документы) — сохраняем как обычные
        # prod-события (текст → save_message, фото/документы → их обработчики)
        # и ТОЛЬКО ПОСЛЕ записи в БД ack'аем. Ack без записи = потеря данных.

        grp = "PRD"
        mtype = msg.get("mediaType") or ""
        sender = msg.get("senderId") or msg.get("senderNumber") or "user"

        ok = False
        # --- Фото ---
        if mtype == "image":
            log(f"[{grp}] PHOTO {mid[:12]}... {_clean_body(msg)[:60]}")
            ok = _save_prod_photo(msg, mid)
        # --- Документ ---
        elif mtype == "document":
            log(f"[{grp}] DOC {mid[:12]}... {msg.get('fileName', '?')}")
            ok = _save_prod_document(msg, mid)
        # --- Прочие медиа (видео/аудио/стикеры/локации) — сырая запись ---
        elif mtype in ("video", "gif", "ptt", "audio", "sticker", "location", "contact"):
            log(f"[{grp}] MEDIA {mtype} {mid[:12]}...")
            local_path = _media_local_path(msg)
            tags = {"msg_id": mid, "media_type": mtype}
            if local_path:
                tags["local_path"] = local_path
            ok = _insert_media_message(PRODUCTION, sender, mtype, mid, tags) is not None
        # --- Текст ---
        else:
            text = extract_text(msg)
            if not text:
                # Пустое событие из боевой (нет текста, нет медиа): факт прихода
                # НЕ теряем — durable-запись в bot_memory_messages ПЕРЕД ack.
                # Только успешная запись → confirmed/ack_ids; при ошибке БД —
                # seen НЕ помечаем и мост НЕ ack'аем (ретрай на следующем тике).
                # Песочница сюда не попадает (continue выше) — не меняется.
                tags = {"msg_id": mid}
                rid = _insert_media_message(PRODUCTION, sender, "empty", mid, tags)
                if rid is None:
                    log(f"[{grp}] EMPTY {mid[:12]}... DB FAIL (arrival not saved) — seen NOT marked, retry next tick")
                    continue
                log(f"[{grp}] EMPTY {mid[:12]}... arrival saved (row {rid})")
                confirmed.append(mid)
                ack_ids.append(mid)
                continue
            log(f"[{grp}] MSG {mid[:12]}...: {text[:100]}")
            ok = _save_prod_text(text, chat_id, mid, sender)

        if ok:
            confirmed.append(mid)
            ack_ids.append(mid)
            new_count += 1
            log(f"[{grp}] SAVED {mtype or 'text'} {mid} → DB")
        else:
            log(f"[{grp}] DB FAIL {mid[:12]}... — seen NOT marked, retry next tick")

    # Durability: seen сохраняется ТОЛЬКО для подтверждённых mid. Если БД была
    # недоступна — mid остаётся вне seen → следующий тик обработает снова.
    if confirmed:
        seen.update(confirmed)
        save_seen(seen)
    # ACK мосту: ТОЛЬКО успешно обработанные (confirmed) — мост удалит их из
    # файлового журнала; не-ack (DB FAIL) восстановятся после рестарта моста.
    if ack_ids:
        send_collect_ack(ack_ids)
    if new_count > 0:
        log(f"[PRD] COLLECTED {new_count}")
    log(f"DONE: {new_count} new")

if __name__ == "__main__":
    main()
