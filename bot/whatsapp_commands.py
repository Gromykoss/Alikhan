#!/usr/bin/env python3
"""
Диспетчер WhatsApp-команд для Alikhan v2.
Слушает песочницу + боевую группу.
ВСЕ сообщения логируются.
Ролевая модель: admin > operator > viewer.
"""
import sys, os, json, time, requests, re, base64, traceback

BRIDGE = "http://127.0.0.1:3000"
SANDBOX = "120363179621030401@g.us"
PRODUCTION = "120363400682390076@g.us"
SEEN_FILE = "/tmp/alikhan_seen.json"
LOG_FILE = "/tmp/alikhan_commands.log"

# --- Ролевая модель ---
ROLE_HIERARCHY = {"admin": 3, "operator": 2, "viewer": 1}


def _load_roles() -> dict:
    """Загрузить роли из authorised_senders.json. Обратная совместимость со старым форматом."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authorized_senders.json")
        with open(path) as f:
            data = json.load(f)
        if "roles" in data:
            return data.get("roles", {})
        elif "authorized_senders" in data:
            # Старый формат — все становятся admin
            return {phone: "admin" for phone in data.get("authorized_senders", [])}
        return {}
    except Exception:
        return {}


ROLES = _load_roles()


def _save_roles() -> bool:
    """Сохранить роли на диск."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authorized_senders.json")
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


def get_messages() -> list:
    try:
        resp = requests.get(f"{BRIDGE}/messages", timeout=5)
        if resp.status_code != 200:
            log(f"BRIDGE HTTP {resp.status_code}")
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log(f"BRIDGE ERR: {e}")
        return []


def send_message(chat_id: str, text: str) -> bool:
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
        today = time.strftime("%Y-%m-%d")
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

        report_day = date.today()
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
                "=", "м3", "м2", "кг", "т ", "шт"]
    return any(w in t for w in triggers)


def handle_qa(text: str, chat_id: str):
    log(f"QA [{chat_id[-12:]}]: '{text[:80]}'")
    try:
        from qa import parse_qa
        today = time.strftime("%Y-%m-%d")
        facts = parse_qa(text, chat_id, today)
        if facts and chat_id == SANDBOX:
            send_message(chat_id, f"✅ Принято: {len(facts)} фактов")
        elif facts:
            log(f"QA: {len(facts)} facts (prod, silent)")
    except Exception as e:
        log(f"QA ERR: {e}\n{traceback.format_exc()}")
        if chat_id == SANDBOX:
            send_message(chat_id, f"❌ Ошибка: {e}")


def main():
    log("START")
    seen = load_seen()
    messages = get_messages()
    log(f"GOT {len(messages)} msgs, {len(seen)} seen")

    new_count = 0
    for msg in messages:
        mid = msg.get("messageId") or msg.get("id")
        if not mid or mid in seen:
            continue
        seen.add(mid)

        if msg.get("fromMe") or msg.get("fromOwner"):
            continue

        chat_id = msg.get("chatId", "")
        is_sandbox = chat_id == SANDBOX
        is_prod = chat_id == PRODUCTION

        if not is_sandbox and not is_prod:
            continue

        grp = "SND" if is_sandbox else "PRD"

        # --- Фото ---
        if msg.get("imageMessage") or msg.get("_media", {}).get("mediaType") == "image":
            log(f"[{grp}] PHOTO {mid[:12]}...")
            new_count += 1
            continue

        # --- Документ ---
        if msg.get("documentMessage") or msg.get("_media", {}).get("mediaType") == "document":
            fname = msg.get("documentMessage", {}).get("fileName", "?")
            log(f"[{grp}] DOC {mid[:12]}... {fname}")
            new_count += 1
            continue

        # --- Текст ---
        text = extract_text(msg)
        if not text:
            log(f"[{grp}] EMPTY {mid[:12]}... — skipping")
            continue

        log(f"[{grp}] MSG {mid[:12]}...: {text[:100]}")

        if is_sandbox:
            if handle_sandbox_command(text, chat_id, msg):
                new_count += 1
                continue
            # QA-факты: только для viewer+ (неавторизованные — мимо)
            if is_qa_text(text) and check_role(msg, "viewer"):
                handle_qa(text, chat_id)
                new_count += 1
                continue
            log(f"[{grp}] UNHANDLED: {text[:80]}")
            if get_role(msg) is not None:
                send_message(chat_id, "❓ Команда не распознана. Доступные: /help")
        else:
            # Production: QA только для viewer+
            if is_qa_text(text) and check_role(msg, "viewer"):
                handle_qa(text, chat_id)
                new_count += 1
                continue

    if new_count:
        save_seen(seen)
    log(f"DONE: {new_count} new")

if __name__ == "__main__":
    main()
