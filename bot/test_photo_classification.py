#!/usr/bin/env python3
"""Short-run verification for the photo classification fix (2026-08-02).

- Exercises _detect_greeting / _normalize_vision_area / _classify_photo_via_vision
  with a stubbed checklist_from_image (no real Grok calls).
- Exercises _save_prod_photo end-to-end with a fake DB module + stubbed
  _insert_media_message (no bridge, no real DB writes).
"""
import os
import sys
import types

BOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT)

import vision_checklist
import whatsapp_commands as wc

FAILED = []


def check(name, cond, detail=""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


# ── 1. _detect_greeting ──────────────────────────────────────────────────────
check("greeting caption detected", wc._detect_greeting("С Днём строителя! 🎉") is True)
check("greeting caption (поздравляем)", wc._detect_greeting("Поздравляем коллектив!") is True)
check("greeting+building caption detected", wc._detect_greeting("АБК поздравляет с Днём строителя") is True)
check("building-only caption NOT greeting", wc._detect_greeting("АБК: бетонирование") is False)
check("building matches in greeting caption", wc._detect_building("АБК поздравляет с Днём строителя") == "АБК")
check("building caption NOT greeting", wc._detect_greeting("Общежитие") is False)
check("empty caption NOT greeting", wc._detect_greeting("") is False)

# ── 2. _normalize_vision_area ────────────────────────────────────────────────
check("vision area canonical", wc._normalize_vision_area("Общежитие") == "Общежитие")
check("vision area canonical (lower)", wc._normalize_vision_area("общий план площадки") == "Общий план")
check("vision area raw kept", wc._normalize_vision_area("Котельная") == "Котельная")
check("vision area empty -> None", wc._normalize_vision_area("") is None)

# ── 3. _classify_photo_via_vision (stubbed checklist_from_image) ────────────
TMP = "/tmp/vision_test_photo.jpg"
with open(TMP, "wb") as f:
    f.write(b"\xff\xd8\xff\xe0fakejpeg")

real_clf = wc._classify_photo_via_vision
real_checklist_from_image = vision_checklist.checklist_from_image


def fake_checklist(result):
    vision_checklist.checklist_from_image = lambda b64, mime="image/jpeg", api_key="": result


def empty_field():
    return {"observed": False, "value": "", "confidence": 0.0}


def obs_field(v):
    return {"observed": True, "value": v, "confidence": 0.9}


# 3a. unrelated (открытка): category=unrelated из vision → «Поздравительная открытка»
fake_checklist({
    "weather_visible": empty_field(), "workers_count": empty_field(),
    "equipment_visible": empty_field(), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": empty_field(),
    "category": obs_field("unrelated"), "category_reason": obs_field("открытка с поздравлением"),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("card checklist -> unrelated + greeting building", k == "unrelated" and cat == "unrelated" and b == wc.GREETING_CARD_BUILDING, f"{b} / {k} / {cat}")

# 3a2. unrelated без явной категории (старый промпт, сигналов нет) → «Постороннее фото»
fake_checklist({
    "weather_visible": obs_field("sunny"), "workers_count": empty_field(),
    "equipment_visible": empty_field(), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": empty_field(),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("no signals fallback -> unrelated", k == "unrelated" and cat == "unrelated" and b == wc.UNRELATED_DEFAULT_BUILDING, f"{b} / {k} / {cat}")

# 3b. стройка с area (category=construction) → building из area_identified
fake_checklist({
    "weather_visible": obs_field("sunny"), "workers_count": obs_field("12"),
    "equipment_visible": empty_field(), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": obs_field("Общежитие"),
    "category": obs_field("construction"), "category_reason": obs_field("монтаж каркаса"),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("construction + area -> building from vision", k == "construction" and cat == "construction" and b == "Общежитие", f"{b} / {k} / {cat}")

# 3c. стройка без area (только workers) → осмысленный дефолт
fake_checklist({
    "weather_visible": empty_field(), "workers_count": obs_field("3"),
    "equipment_visible": empty_field(), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": empty_field(),
    "category": obs_field("construction"), "category_reason": obs_field("рабочие на объекте"),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("construction no area -> default building", k == "construction" and b == wc.CONSTRUCTION_DEFAULT_BUILDING, f"{b} / {k}")

# 3c2. fallback без category: только workers → construction
fake_checklist({
    "weather_visible": empty_field(), "workers_count": obs_field("3"),
    "equipment_visible": empty_field(), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": empty_field(),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("fallback workers -> construction", k == "construction" and b == wc.CONSTRUCTION_DEFAULT_BUILDING, f"{b} / {k}")

# 3d. site_related: категория из vision (материалы/техника/бытовки) → НЕ стройка
fake_checklist({
    "weather_visible": empty_field(), "workers_count": empty_field(),
    "equipment_visible": obs_field("КамАЗ с арматурой"), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": empty_field(),
    "category": obs_field("site_related"), "category_reason": obs_field("склад арматуры"),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("site_related explicit -> site_related + description", k == "site_related" and cat == "site_related" and desc == "склад арматуры", f"{b} / {k} / {cat} / {desc}")
check("site_related building default", b == wc.SITE_RELATED_DEFAULT_BUILDING, b)

# 3d2. fallback без category: только техника (equipment) → site_related
fake_checklist({
    "weather_visible": empty_field(), "workers_count": empty_field(),
    "equipment_visible": obs_field("экскаватор"), "progress_vs_plan": empty_field(),
    "safety_issues": empty_field(), "area_identified": empty_field(),
})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("fallback equipment-only -> site_related", k == "site_related" and cat == "site_related", f"{b} / {k} / {cat}")

# 3e. _error checklist → vision_unavailable
fake_checklist({"_error": "empty response"})
b, k, cat, desc = wc._classify_photo_via_vision(TMP, "image/jpeg")
check("checklist _error -> vision_unavailable", k == "vision_unavailable" and b == wc.VISION_UNAVAILABLE_BUILDING and cat is None, f"{b} / {k} / {cat}")

# 3f. исключение (файл битый) → vision_unavailable
b, k, cat, desc = wc._classify_photo_via_vision("/tmp/does_not_exist_12345.jpg", "image/jpeg")
check("vision exception -> vision_unavailable", k == "vision_unavailable" and b == wc.VISION_UNAVAILABLE_BUILDING, f"{b} / {k}")

# restore
vision_checklist.checklist_from_image = real_checklist_from_image

# ── 4. _save_prod_photo end-to-end (fake DB + stubbed inserts) ──────────────
class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        last = self.executed[-1][0] if self.executed else ""
        if "ojr_title_page" in last:
            return (7,)  # активный title_id
        return None  # ojr_photo_log SELECT → запись отсутствует

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


fake_db = types.ModuleType("db")
fake_conn_holder = {}
setattr(fake_db, "get_conn", lambda: fake_conn_holder["conn"])
sys.modules["db"] = fake_db

inserted_memory = []
wc._insert_media_message = lambda chat, sender, mtype, mid, tags: (
    inserted_memory.append((chat, sender, mtype, mid, tags)) or 1001
)
orig_classify = wc._classify_photo_via_vision
orig_local = wc._media_local_path


def run_photo(msg, classify_result=None):
    fake_conn_holder["conn"] = FakeConn()
    inserted_memory.clear()
    if classify_result is not None:
        wc._classify_photo_via_vision = lambda p, m: classify_result
    try:
        return wc._save_prod_photo(msg, msg["mid"]), fake_conn_holder["conn"]
    finally:
        wc._classify_photo_via_vision = orig_classify


# 4a. Открытка с caption-поздравлением: память есть, ojr НЕТ
ok, conn = run_photo({"mid": "M-CARD1", "body": "С Днём строителя! 🎉", "mediaUrls": [TMP]})
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("card: returns True", ok is True)
check("card: ojr_photo_log NOT inserted", len(ojr_inserts) == 0, f"inserts={len(ojr_inserts)}")
check("card: memory tags building", inserted_memory and inserted_memory[0][4]["building"] == wc.GREETING_CARD_BUILDING,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("card: memory tags classification", inserted_memory and inserted_memory[0][4].get("classification") == "greeting_card",
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("card: memory tags category=unrelated", inserted_memory and inserted_memory[0][4].get("category") == wc.CATEGORY_UNRELATED,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("card: memory tags category_description", inserted_memory and inserted_memory[0][4].get("category_description") == "Поздравительная открытка",
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4a2. «АБК поздравляет с Днём строителя» (greeting + building в caption):
#      greeting ПЕРВЫМ — открытка, НЕ стройка, vision НЕ вызывается (замечание Codex).
#      classify_result=construction — если бы vision вызывалась, тест бы упал.
ok, conn = run_photo({"mid": "M-GBLD1", "body": "АБК поздравляет с Днём строителя", "mediaUrls": [TMP]},
                     classify_result=("АБК", "construction", "construction", None))
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("greeting+building caption: ojr NOT inserted", len(ojr_inserts) == 0, f"inserts={len(ojr_inserts)}")
check("greeting+building caption: building=Поздравительная открытка", inserted_memory and inserted_memory[0][4]["building"] == wc.GREETING_CARD_BUILDING,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("greeting+building caption: classification=greeting_card", inserted_memory and inserted_memory[0][4].get("classification") == "greeting_card",
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("greeting+building caption: category=unrelated", inserted_memory and inserted_memory[0][4].get("category") == wc.CATEGORY_UNRELATED,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4a3. «АБК: бетонирование» → стройка (НЕ открытка), файла нет → caption-здание АБК
ok, conn = run_photo({"mid": "M-BET1", "body": "АБК: бетонирование"})
ojr_params = [e[1] for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("'АБК: бетонирование' (no file): ojr inserted", len(ojr_params) == 1)
check("'АБК: бетонирование' (no file): building=АБК", ojr_params and ojr_params[0][2] == "АБК",
      str(ojr_params[0]) if ojr_params else "none")
check("'АБК: бетонирование' (no file): no classification tag (caption path)", inserted_memory and inserted_memory[0][4].get("classification") is None,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4a4. «АБК: бетонирование» + файл → vision-стройка в ojr
ok, conn = run_photo({"mid": "M-BET2", "body": "АБК: бетонирование", "mediaUrls": [TMP]},
                     classify_result=("АБК", "construction", "construction", None))
ojr_params = [e[1] for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("'АБК: бетонирование' + file: ojr inserted (vision)", len(ojr_params) == 1 and ojr_params[0][2] == "АБК",
      str(ojr_params[0]) if ojr_params else "none")

# 4b. Caption-здание БЕЗ файла (vision недоступна) → fallback на caption: ojr пишется
ok, conn = run_photo({"mid": "M-BLD1", "body": "Фото Общежитие"})
ojr_params = [e[1] for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("caption building (no file): ojr inserted", len(ojr_params) == 1)
check("caption building (no file): building=Общежитие", ojr_params and ojr_params[0][2] == "Общежитие", str(ojr_params[0]) if ojr_params else "none")
check("caption building (no file): no classification tag (caption path)", inserted_memory and inserted_memory[0][4].get("classification") is None,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("caption building (no file): memory tags category=construction", inserted_memory and inserted_memory[0][4].get("category") == wc.CATEGORY_CONSTRUCTION,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4b2. Caption-здание + файл → vision имеет приоритет: building из vision в ojr
ok, conn = run_photo({"mid": "M-BLD2", "body": "Общий план", "mediaUrls": [TMP]}, classify_result=("АБК", "construction", "construction", None))
ojr_params = [e[1] for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("caption building + file: vision used (building=АБК)", len(ojr_params) == 1 and ojr_params[0][2] == "АБК",
      str(ojr_params[0]) if ojr_params else "none")

# 4c. Vision: стройка без caption → ojr пишется с building из vision
ok, conn = run_photo({"mid": "M-VIS1", "body": "", "mediaUrls": [TMP]}, classify_result=("Галерея", "construction", "construction", None))
ojr_params = [e[1] for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("vision construction: ojr inserted", len(ojr_params) == 1)
check("vision construction: building=Галерея", ojr_params and ojr_params[0][2] == "Галерея", str(ojr_params[0]) if ojr_params else "none")

# 4d. Vision: unrelated (открытка) → ojr НЕ пишется, память с тегом category=unrelated
ok, conn = run_photo({"mid": "M-VIS2", "body": "", "mediaUrls": [TMP]}, classify_result=("Поздравительная открытка", "unrelated", "unrelated", "открытка с поздравлением"))
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("vision card: returns True", ok is True)
check("vision card: ojr NOT inserted", len(ojr_inserts) == 0)
check("vision card: memory classification tag", inserted_memory and inserted_memory[0][4].get("classification") == "unrelated")
check("vision card: memory category=unrelated", inserted_memory and inserted_memory[0][4].get("category") == wc.CATEGORY_UNRELATED)

# 4e. Vision недоступен → «Фото (описание недоступно)», ojr НЕ пишется
ok, conn = run_photo({"mid": "M-UN1", "body": "", "mediaUrls": [TMP]}, classify_result=("Фото (описание недоступно)", "vision_unavailable", None, None))
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("vision unavailable: returns True", ok is True)
check("vision unavailable: ojr NOT inserted", len(ojr_inserts) == 0)
check("vision unavailable: building NOT 'Общий план'", inserted_memory and inserted_memory[0][4]["building"] == "Фото (описание недоступно)",
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("vision unavailable: memory classification tag", inserted_memory and inserted_memory[0][4].get("classification") == "vision_unavailable")
check("vision unavailable: no category tag", inserted_memory and "category" not in inserted_memory[0][4],
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4f. mediaMissing (файла нет) → vision невозможен → «Фото (описание недоступно)», ojr НЕ пишется
ok, conn = run_photo({"mid": "M-NOF", "body": "", "mediaMissing": True})
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("mediaMissing: returns True", ok is True)
check("mediaMissing: ojr NOT inserted", len(ojr_inserts) == 0)
check("mediaMissing: building NOT 'Общий план'", inserted_memory and inserted_memory[0][4]["building"] == "Фото (описание недоступно)",
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4g. Vision: site_related (материалы/техника/бытовки) → ojr НЕ пишется, память с category=site_related + описанием
ok, conn = run_photo({"mid": "M-SITE1", "body": "", "mediaUrls": [TMP]}, classify_result=("Связано с объектом (не стройка)", "site_related", "site_related", "склад арматуры"))
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("site_related: returns True", ok is True)
check("site_related: ojr NOT inserted", len(ojr_inserts) == 0)
check("site_related: memory category=site_related", inserted_memory and inserted_memory[0][4].get("category") == wc.CATEGORY_SITE_RELATED,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("site_related: memory category_description", inserted_memory and inserted_memory[0][4].get("category_description") == "склад арматуры",
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("site_related: memory building tag", inserted_memory and inserted_memory[0][4]["building"] == wc.SITE_RELATED_DEFAULT_BUILDING,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

# 4h. Vision: unrelated (мем/личное) → «Постороннее фото», ojr НЕ пишется
ok, conn = run_photo({"mid": "M-MEME", "body": "", "mediaUrls": [TMP]}, classify_result=("Постороннее фото", "unrelated", "unrelated", "личное фото"))
ojr_inserts = [e for e in conn.cur.executed if "INSERT INTO ojr_photo_log" in e[0]]
check("unrelated meme: ojr NOT inserted", len(ojr_inserts) == 0)
check("unrelated meme: memory building=Постороннее фото", inserted_memory and inserted_memory[0][4]["building"] == wc.UNRELATED_DEFAULT_BUILDING,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")
check("unrelated meme: memory category=unrelated", inserted_memory and inserted_memory[0][4].get("category") == wc.CATEGORY_UNRELATED,
      str(inserted_memory[0][4]) if inserted_memory else "no memory row")

print()
if FAILED:
    print(f"RESULT: {len(FAILED)} FAILED — {FAILED}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
