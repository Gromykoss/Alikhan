"""STT module: transcribe_audio(b64_audio) → corrected_text"""
import time, requests, json, sys, os, base64, tempfile, subprocess
import re
import urllib.request
from datetime import datetime
from config import EVO, KEY  # Bridge API (was bridge_wrapper, removed)
SANDBOX = os.environ.get("WHATSAPP_SANDBOX", "")

sys.stdout.reconfigure(line_buffering=True)

_model = None

def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model

def transcribe_audio(b64_audio, audio_format=None):
    """STT via faster-whisper + Grok post-correction"""
    source_path = wav_path = None
    try:
        suffix = "." + (audio_format or "ogg").lower().lstrip(".")
        if suffix not in {".ogg", ".mp4", ".aac"}:
            suffix = ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(base64.b64decode(b64_audio))
            source_path = f.name
        wav_path = source_path + ".wav"
        subprocess.run(["ffmpeg", "-y", "-i", source_path, "-ar", "16000", "-ac", "1", wav_path],
                       capture_output=True, check=True)
        segments, _ = _get_model().transcribe(wav_path, language="ru")
        segments = list(segments)
        if not segments or all(getattr(s, "no_speech_prob", 0) >= 0.6 for s in segments):
            return ""
        raw = " ".join(s.text for s in segments).strip()
        if not raw:
            return ""
        # Post-correct via Grok
        from handlers import ask_grok
        corrected = ask_grok(
            f"Исправь опечатки и ошибки распознавания в тексте. "
            f"Скорее всего там имя «Алихан» (голосовой ассистент). "
            f"Также исправь искажённые вопросные слова: такая→какая, такой→какой, че→что, скока→сколько. "
            f"Все числа и последовательности цифр сохрани в точности: не добавляй, не удаляй и не заменяй цифры. "
            f"Верни ТОЛЬКО исправленный текст, без пояснений:\n\n{raw}",
            max_tokens=200
        ).strip()
        if re.findall(r"\d+", corrected) != re.findall(r"\d+", raw):
            corrected = raw
        print(f"[STT] raw={raw[:80]} => corrected={corrected[:80]}", flush=True)
        return corrected if corrected else raw
    except Exception as e:
        print(f"[STT ERR] {e}", flush=True)
        return ""
    finally:
        for path in (source_path, wav_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
