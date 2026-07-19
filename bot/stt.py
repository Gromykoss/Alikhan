"""STT module: transcribe_audio(b64_audio) → corrected_text"""
import time, requests, json, sys, os, base64, tempfile, subprocess
import re
import urllib.request
from datetime import datetime
from secret_config import get_evo_key

EVO = "http://127.0.0.1:8080"
KEY = get_evo_key(required=True)
SANDBOX = os.environ.get("WHATSAPP_SANDBOX", "")

sys.stdout.reconfigure(line_buffering=True)

def transcribe_audio(b64_audio):
    """STT via faster-whisper + Grok post-correction"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(base64.b64decode(b64_audio))
            ogg_path = f.name
        wav_path = ogg_path.replace(".ogg", ".wav")
        subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
                       capture_output=True, check=True)
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(wav_path, language="ru")
        raw = " ".join(s.text for s in segments).strip()
        os.unlink(ogg_path); os.unlink(wav_path)
        if not raw:
            return ""
        # Post-correct via Grok
        from handlers import ask_grok
        corrected = ask_grok(
            f"Исправь опечатки и ошибки распознавания в тексте. "
            f"Скорее всего там имя «Алихан» (голосовой ассистент). "
            f"Также исправь искажённые вопросные слова: такая→какая, такой→какой, че→что, скока→сколько. "
            f"Верни ТОЛЬКО исправленный текст, без пояснений:\n\n{raw}",
            max_tokens=200
        ).strip()
        print(f"[STT] raw={raw[:80]} => corrected={corrected[:80]}", flush=True)
        return corrected if corrected else raw
    except Exception as e:
        print(f"[STT ERR] {e}", flush=True)
        return ""
