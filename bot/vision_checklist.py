"""
Structured vision checklist for Alikhan construction site photos.

Pattern #5 from T-137 fantasy study.

Replaces plain text photo descriptions with structured JSON checklists
that map directly to ЕЖО (Ежедневный Журнал Отчётов) columns.

Usage:
    from vision_checklist import checklist_from_image, checklist_to_ejo_map

    # Get structured analysis from a Grok vision response
    checklist = checklist_from_image(image_base64, mimetype="image/jpeg")
    # {"weather_visible": {"observed": true, "value": "sunny", "confidence": 0.85}, ...}

    # Map checklist fields to ЕЖО columns
    ejo_data = checklist_to_ejo_map(checklist)
    # {"C": "sunny", "workers": 12, "equipment": "2 excavators, 1 crane", ...}
"""
import base64
import json
import os
import re
import urllib.request
from typing import Any, Dict, Optional

XAI_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_XAI_KEY = os.environ.get("XAI_API_KEY", os.environ.get("XAI_KEY", ""))

CHECKLIST_SCHEMA = {
    "weather_visible": "string describing sky conditions (sunny/cloudy/rain/snow/fog)",
    "workers_count": "number - estimated count of workers visible",
    "equipment_visible": "string - list of equipment/machinery visible",
    "progress_vs_plan": "string - visible progress relative to expected stage",
    "safety_issues": "string - any visible safety concerns (missing PPE, unsafe scaffolding, etc.)",
    "area_identified": "string - which building area/section is shown",
}

# Prompt that forces Grok to respond in structured JSON
CHECKLIST_PROMPT = """You are analyzing a construction site photo for a daily report (ЕЖО). 
Respond with ONLY a JSON object, no markdown, no explanation.

Structure:
{
  "weather_visible": {"observed": true/false, "value": "description", "confidence": 0.0-1.0},
  "workers_count": {"observed": true/false, "value": "number or description", "confidence": 0.0-1.0},
  "equipment_visible": {"observed": true/false, "value": "list of equipment", "confidence": 0.0-1.0},
  "progress_vs_plan": {"observed": true/false, "value": "visible progress assessment", "confidence": 0.0-1.0},
  "safety_issues": {"observed": true/false, "value": "any safety concerns visible", "confidence": 0.0-1.0},
  "area_identified": {"observed": true/false, "value": "building/section name", "confidence": 0.0-1.0}
}

Rules:
- observed=true only if you can clearly see it in the photo
- confidence: 0.5=unsure, 0.7=likely, 0.9+=clearly visible
- weather_visible only if sky/conditions visible in frame
- workers_count: count what you can see, write "none visible" if 0
- area_identified: use Russian names (Общежитие, АБК, Галерея, Общий план) if recognizable
- safety_issues: note missing helmets, unsafe scaffolding, open trenches, missing barriers
- progress_vs_plan: compare visible state to what should be done at this stage of a building construction

Respond with JSON only."""


EJO_COLUMN_MAP = {
    # Field -> (EJO section, column or target)
    "weather_visible": ("Погода", "D"),      # Column D = weather conditions
    "workers_count": ("Раздел 1", "Итого"),   # Section 1 = personnel total
    "equipment_visible": ("Раздел 3", "J"),   # Column J = equipment/machinery
    "progress_vs_plan": ("Раздел 3", "M"),    # Column M = actual work completed
    "safety_issues": ("Раздел 4", "notes"),   # Section 4 = construction control
    "area_identified": ("Здание", "area"),    # Building identification
}


def _call_grok_vision(image_base64: str, mimetype: str = "image/jpeg",
                      api_key: str = "") -> Optional[str]:
    """Call Grok vision API with a base64 image. Returns JSON string or None."""
    if not api_key:
        api_key = DEFAULT_XAI_KEY
    if not api_key:
        return None

    payload = {
        "model": "grok-2-vision-latest",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CHECKLIST_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mimetype};base64,{image_base64}"},
                    },
                ],
            }
        ],
        "max_tokens": 800,
        "temperature": 0.1,  # Low temp for structured output
    }
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        XAI_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip()
    except Exception:
        return None


def _parse_checklist_json(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """Parse a raw Grok response into the checklist dict.

    Handles markdown-wrapped JSON (```json ... ```) and malformed responses.
    Returns the checklist dict or an error dict.
    """
    if not raw_text:
        return {"_error": "empty response", "_raw": ""}

    # Try direct JSON parse first
    try:
        data = json.loads(raw_text)
        return _validate_checklist(data)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return _validate_checklist(data)
        except json.JSONDecodeError:
            pass

    # Try to find JSON-like object in text
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return _validate_checklist(data)
        except json.JSONDecodeError:
            pass

    return {"_error": "could not parse JSON", "_raw": raw_text[:500]}


def _validate_checklist(data: dict) -> dict:
    """Validate and normalize a checklist dict. Fills missing fields."""
    result = {}
    for field in CHECKLIST_SCHEMA:
        entry = data.get(field, {})
        if not isinstance(entry, dict):
            entry = {}
        result[field] = {
            "observed": bool(entry.get("observed", False)),
            "value": str(entry.get("value", "")),
            "confidence": float(entry.get("confidence", 0.0)),
        }
    return result


def checklist_from_image(image_base64: str, mimetype: str = "image/jpeg",
                         api_key: str = "") -> Dict[str, Dict[str, Any]]:
    """Generate a structured vision checklist from a base64-encoded image.

    Args:
        image_base64: Base64-encoded image data.
        mimetype: Image MIME type (default: image/jpeg).
        api_key: xAI API key. Falls back to XAI_API_KEY env var.

    Returns:
        Checklist dict with fields: weather_visible, workers_count,
        equipment_visible, progress_vs_plan, safety_issues, area_identified.
        Each field = {"observed": bool, "value": str, "confidence": float}.
    """
    raw = _call_grok_vision(image_base64, mimetype, api_key)
    return _parse_checklist_json(raw or "")


def checklist_from_description(description_text: str) -> Dict[str, Dict[str, Any]]:
    """Convert an existing plain-text photo description into a checklist.

    Useful for backward compatibility — processes descriptions already
    stored in the database from the old plain-text pipeline.

    Attempts heuristic extraction of structured fields from free text.
    """
    result = {}
    text_lower = description_text.lower()

    # Weather
    weather_words = [w for w in ["солнечно", "sunny", "пасмурно", "cloudy",
                                   "дождь", "rain", "снег", "snow", "туман", "fog",
                                   "ясно", "clear"]
                     if w in text_lower]
    result["weather_visible"] = {
        "observed": len(weather_words) > 0,
        "value": ", ".join(weather_words) if weather_words else "",
        "confidence": 0.6 if weather_words else 0.0,
    }

    # Workers
    worker_match = re.search(r"(\d+)\s*(?:человек|рабочих|рабочий|workers|people)", text_lower)
    result["workers_count"] = {
        "observed": worker_match is not None,
        "value": worker_match.group(1) if worker_match else "не определено",
        "confidence": 0.7 if worker_match else 0.2,
    }

    # Equipment
    equipment_keywords = ["экскаватор", "excavator", "кран", "crane", "бульдозер", "bulldozer",
                          "самосвал", "dump truck", "бетономешалка", "concrete mixer",
                          "погрузчик", "loader", "компрессор", "compressor"]
    found_equip = [e for e in equipment_keywords if e in text_lower]
    result["equipment_visible"] = {
        "observed": len(found_equip) > 0,
        "value": ", ".join(found_equip) if found_equip else "",
        "confidence": 0.6 if found_equip else 0.2,
    }

    # Area
    areas = ["общежитие", "dormitory", "абк", "abk", "галерея", "gallery",
             "общий план", "general plan", "котельная", "boiler"]
    found_areas = [a for a in areas if a in text_lower]
    result["area_identified"] = {
        "observed": len(found_areas) > 0,
        "value": ", ".join(found_areas) if found_areas else "не определено",
        "confidence": 0.7 if found_areas else 0.3,
    }

    # Safety
    safety_keywords = ["без каски", "no helmet", "no ppe", "опасно", "danger",
                       "ограждение", "barrier", "открытый котлован", "open trench"]
    found_safety = [s for s in safety_keywords if s in text_lower]
    result["safety_issues"] = {
        "observed": len(found_safety) > 0,
        "value": ", ".join(found_safety) if found_safety else "не выявлено",
        "confidence": 0.5 if found_safety else 0.3,
    }

    # Progress
    progress_keywords = ["отставание", "delay", "опережение", "ahead", "по графику", "on schedule"]
    found_progress = [p for p in progress_keywords if p in text_lower]
    result["progress_vs_plan"] = {
        "observed": len(found_progress) > 0,
        "value": ", ".join(found_progress) if found_progress else "не указано",
        "confidence": 0.5 if found_progress else 0.2,
    }

    return result


def checklist_to_ejo_map(checklist: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Map checklist fields to ЕЖО column targets.

    Args:
        checklist: The output of checklist_from_image() or checklist_from_description().

    Returns:
        Dict mapping logical EJO targets to values.
        e.g. {"weather": "sunny", "workers": "12", "equipment": "2 excavators",
              "progress": "on schedule", "safety": "no issues", "area": "Общежитие"}
    """
    mapping = {}

    w = checklist.get("weather_visible", {})
    if w.get("observed") and w.get("value"):
        mapping["weather"] = w["value"]

    workers = checklist.get("workers_count", {})
    if workers.get("observed") and workers.get("value"):
        mapping["workers"] = workers["value"]

    equip = checklist.get("equipment_visible", {})
    if equip.get("observed") and equip.get("value"):
        mapping["equipment"] = equip["value"]

    progress = checklist.get("progress_vs_plan", {})
    if progress.get("observed") and progress.get("value"):
        mapping["progress"] = progress["value"]

    safety = checklist.get("safety_issues", {})
    if safety.get("observed") and safety.get("value"):
        mapping["safety"] = safety["value"]

    area = checklist.get("area_identified", {})
    if area.get("observed") and area.get("value"):
        mapping["area"] = area["value"]

    return mapping


def checklist_to_text(checklist: Dict[str, Dict[str, Any]]) -> str:
    """Format a checklist as a compact human-readable string for WhatsApp replies.

    Example output:
        📷 Фото: Общежитие
        🌤 Солнечно (85%)
        👷 12 рабочих
        🏗 2 экскаватора, 1 кран
        ⚠️ Без касок
        📊 По графику
    """
    lines = []
    area = checklist.get("area_identified", {})
    if area.get("value"):
        lines.append(f"📷 Фото: {area['value']}")

    w = checklist.get("weather_visible", {})
    if w.get("observed") and w.get("value"):
        lines.append(f"🌤 {w['value']} ({int(w.get('confidence', 0) * 100)}%)")

    workers = checklist.get("workers_count", {})
    if workers.get("observed") and workers.get("value"):
        lines.append(f"👷 {workers['value']}")

    equip = checklist.get("equipment_visible", {})
    if equip.get("observed") and equip.get("value"):
        lines.append(f"🏗 {equip['value']}")

    safety = checklist.get("safety_issues", {})
    if safety.get("observed") and safety.get("value") and safety["value"] != "не выявлено":
        lines.append(f"⚠️ {safety['value']}")

    progress = checklist.get("progress_vs_plan", {})
    if progress.get("observed") and progress.get("value"):
        lines.append(f"📊 {progress['value']}")

    return "\n".join(lines) if lines else "📷 Фото получено, анализ не дал результатов"
