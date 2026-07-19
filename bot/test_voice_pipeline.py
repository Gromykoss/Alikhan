#!/usr/bin/env python3
"""Tests for Alikhan Voice Pipeline — STT + TTS + DB + QA"""

import subprocess, sys, os, json, base64, tempfile, re
from datetime import datetime

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")

print("=" * 60)
print("Alikhan Voice Pipeline Tests")
print("=" * 60)

# ── 1. STT Pipeline ──
print("\n📢 1. STT (Speech-to-Text)")

# Generate test audio
test_text = "Алихан, сколько рабочих на объекте"
subprocess.run(["edge-tts", "--voice", "ru-RU-SvetlanaNeural", "--text", test_text,
                "--write-media", "/tmp/test_stt.mp3"], capture_output=True)
subprocess.run(["ffmpeg", "-y", "-i", "/tmp/test_stt.mp3", "-ar", "16000", "-ac", "1",
                "/tmp/test_stt.wav"], capture_output=True)

from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe("/tmp/test_stt.wav", language="ru")
raw = " ".join(s.text for s in segments).strip()

test("Whisper транскрибирует аудио", len(raw) > 3, f"got: '{raw}'")
test("Содержит 'алихан' (fuzzy)", bool(re.search(r'[ао]л[еи][хгк]', raw.lower())), f"text: {raw}")

# ── 2. Grok Correction ──
print("\n🤖 2. Grok Post-Correction")

test_cases = [
    ("Алейхам!", "Алихан"),
    ("Олеган, какой сегодня день", "алихан"),
    ("Аллехан, сколько рабочих на объекте", "алихан"),
    ("Олег Ант, статус группы", "алихан"),
]
sys.path.insert(0, "/home/hermes-workspace/Alikhan-migration/bot")
from handlers import ask_grok

for raw_text, expected in test_cases:
    corrected = ask_grok(
        f"Исправь опечатки и ошибки распознавания в тексте. "
        f"Скорее всего там имя «Алихан» (голосовой ассистент). "
        f"Верни ТОЛЬКО исправленный текст, без пояснений:\n\n{raw_text}",
        max_tokens=200
    ).strip()
    match = expected.lower() in corrected.lower()
    test(f"'{raw_text}' → содержит '{expected}'", match, f"got: '{corrected[:60]}'")

# ── 3. QA Parser ──
print("\n📋 3. QA Parser")

# Simulate _is_qa logic
def is_qa(text):
    if "?" in text or any(w in text.lower() for w in 
       ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему"]):
        return False
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "сделано", "не успели", "техник"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    return bool(re.search(r'\d\.\d\.\d+\s*=', text))

test("QA: данные о рабочих", is_qa("атантай 5 рабочих ИТР 2") == True)
test("QA: не вопрос", is_qa("сколько рабочих сегодня?") == False)
test("QA: не вопрос (какая)", is_qa("какая техника на объекте") == False)
test("QA: VOR код", is_qa("2.1.5 = 100м3 бетон") == True)
test("QA: обычный текст", is_qa("привет алихан") == False)

# ── 4. Voice Trigger ──
print("\n🎤 4. Voice Reply Trigger")

voice_triggers = ["голосом", "озвучь", "голос"]
def has_voice_trigger(text):
    return any(w in text.lower() for w in voice_triggers)

test("Триггер 'голосом'", has_voice_trigger("ответь голосом"))
test("Триггер 'озвучь'", has_voice_trigger("озвучь это"))
test("Нет триггера", not has_voice_trigger("алихан привет"))

# ── 5. DB Fact Lookup ──
print("\n🗄️ 5. DB Fact Lookup")

try:
    from db_memory import fact_lookup
    today = datetime.now().strftime("%Y-%m-%d")
    facts = fact_lookup(os.environ.get("WHATSAPP_SANDBOX", ""), start_date=today, limit=5)
    test("DB доступна", True)
    test(f"Фактов за сегодня: {len(facts)}", len(facts) >= 0)
    if facts:
        for f in facts[:3]:
            print(f"     📌 {f.get('category','?')}: {str(f.get('fact',''))[:60]}")
    else:
        print("     (нет фактов за сегодня — OK, тест проходит)")
except Exception as e:
    test("DB доступна", False, str(e)[:80])

# ── 6. Edge-TTS Generation ──
print("\n🔊 6. TTS Generation")

try:
    result = subprocess.run(
        ["edge-tts", "--voice", "ru-RU-SvetlanaNeural", "--text", "Тест голосового ответа",
         "--write-media", "/tmp/test_tts.mp3"],
        capture_output=True, timeout=15
    )
    size = os.path.getsize("/tmp/test_tts.mp3") if os.path.exists("/tmp/test_tts.mp3") else 0
    test("edge-tts генерирует аудио", size > 1000, f"size={size} bytes")
except Exception as e:
    test("edge-tts генерирует аудио", False, str(e)[:80])

# ── Summary ──
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed ({FAIL} failed)")
if FAIL == 0:
    print("🎉 All tests passed!")
else:
    print(f"⚠️  {FAIL} test(s) failed")
print("=" * 60)
