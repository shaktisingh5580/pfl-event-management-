"""
agents/complaint_agent.py
NLP-powered complaint categorization and logging for the AI Event Help-Desk.

Flow:
  1. Send complaint text to LLM → get structured JSON (category, severity, summary, location)
  2. Persist the row to Supabase `complaints` table via supabase_tool
  3. Return the saved row (with UUID) for use in bot notifications

Categories : Technical | Logistics | Facilities | Emergency | Other
Severities : low | medium | high | emergency
"""

import json
import re
from datetime import datetime, timezone


# ─── LLM helper ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an AI Help-Desk assistant for a student tech event.

Analyse the complaint message below and reply ONLY with a compact JSON object — no markdown, no extra text.

Required JSON fields:
  "category"  : one of ["Technical", "Logistics", "Facilities", "Emergency", "Other"]
  "severity"  : one of ["low", "medium", "high", "emergency"]
  "summary"   : one-line plain-English summary (≤ 15 words)
  "location"  : the physical location mentioned, or "" if none

Rules for severity:
  - "emergency"  → medical, fire, safety threat, or the word "emergency / urgent / SOS"
  - "high"       → event-blocking (no food, broken equipment, hall unusable)
  - "medium"     → inconvenient but workable (WiFi slow, seat issue)
  - "low"        → minor feedback or unclear complaint

Example output:
{"category":"Facilities","severity":"high","summary":"AC is broken in Hall B","location":"Hall B"}
"""


def _call_llm(text: str) -> dict:
    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    from openai import OpenAI

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": text},
        ],
        max_tokens=120,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()

    # Strip any accidental markdown code fences
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    return json.loads(raw)


def _fallback_categorize(text: str) -> dict:
    """Keyword-based fallback when LLM is unavailable."""
    text_l = text.lower()
    if any(w in text_l for w in ["emergency", "sos", "fire", "medical", "hurt", "accident"]):
        category, severity = "Emergency", "emergency"
    elif any(w in text_l for w in ["wifi", "internet", "laptop", "code judge", "system", "technical", "bug", "error"]):
        category, severity = "Technical", "high"
    elif any(w in text_l for w in ["food", "coupon", "registration", "badge", "schedule", "bus"]):
        category, severity = "Logistics", "medium"
    elif any(w in text_l for w in ["ac", "fan", "light", "toilet", "washroom", "hall", "room", "chair"]):
        category, severity = "Facilities", "medium"
    else:
        category, severity = "Other", "low"

    return {
        "category": category,
        "severity": severity,
        "summary":  text[:80] + ("…" if len(text) > 80 else ""),
        "location": "",
    }


# ─── Main entry point ────────────────────────────────────────────────────────

async def categorize_and_log_complaint(
    text: str,
    telegram_id: int,
    telegram_username: str,
    attendee_id: str | None = None,
) -> dict:
    """
    Categorize `text` with LLM (fallback to keyword rules) and log it to Supabase.

    Returns the persisted complaint row dict, which includes the UUID `id`.
    The row is returned even if the DB write fails (id will be None in that case).
    """

    # 1. NLP categorization
    try:
        parsed = _call_llm(text)
        # Validate / clamp values
        valid_cats  = {"Technical", "Logistics", "Facilities", "Emergency", "Other"}
        valid_sevs  = {"low", "medium", "high", "emergency"}
        category = parsed.get("category", "Other") if parsed.get("category") in valid_cats else "Other"
        severity = parsed.get("severity", "medium") if parsed.get("severity") in valid_sevs else "medium"
        summary  = str(parsed.get("summary", text[:80]))
        location = str(parsed.get("location", ""))
    except Exception as e:
        print(f"[ComplaintAgent] LLM error ({e}), using keyword fallback")
        parsed   = _fallback_categorize(text)
        category = parsed["category"]
        severity = parsed["severity"]
        summary  = parsed["summary"]
        location = parsed["location"]

    # 2. Persist to Supabase
    row = {
        "telegram_id":       telegram_id,
        "telegram_username": telegram_username.lstrip("@") if telegram_username else "",
        "attendee_id":       attendee_id,
        "category":          category,
        "severity":          severity,
        "description":       text,
        "summary":           summary,
        "location":          location,
        "status":            "open",
    }

    try:
        from tools.supabase_tool import log_complaint
        saved = log_complaint(row)
        print(f"[ComplaintAgent] Logged complaint {saved['id']} — {category}/{severity}")
        return saved
    except Exception as e:
        print(f"[ComplaintAgent] DB error ({e}), returning unsaved row")
        row["id"] = None
        return row
