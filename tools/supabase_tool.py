"""
tools/supabase_tool.py
All Supabase read/write operations for the AI Event Management System.
Covers: attendees, check-ins, wall photos, certificates, feedback, matchmaking.
"""
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
import uuid


def _client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# ─────────────────────────────────────────────────────────────
#  ATTENDEES
# ─────────────────────────────────────────────────────────────

def register_attendee(data: dict) -> dict:
    """
    Insert a new attendee row. data keys:
    name, email, phone, skills, interests, goals, telegram_id, seat, coordinator
    Returns the created row (with its UUID).
    """
    res = _client().table("attendees").insert(data).execute()
    return res.data[0]


def get_attendee_by_id(attendee_id: str) -> dict | None:
    res = _client().table("attendees").select("*").eq("id", attendee_id).single().execute()
    return res.data


def get_attendee_by_telegram(telegram_id: int) -> dict | None:
    res = _client().table("attendees").select("*").eq("telegram_id", telegram_id).maybe_single().execute()
    return res.data


def get_attendee_by_username(username: str) -> dict | None:
    """
    Look up an attendee by their Telegram username (stored during website registration).
    Strips leading @ if present. Returns None if not found.
    """
    clean = username.lstrip("@").lower()
    res = (
        _client().table("attendees")
        .select("*")
        .ilike("telegram_username", clean)   # case-insensitive match
        .maybe_single()
        .execute()
    )
    return res.data


def update_telegram_id(attendee_id: str, telegram_id: int) -> None:
    """
    Called when a website-registered attendee first messages the bot.
    Saves their numeric telegram_id so the bot can DM them in future.
    """
    _client().table("attendees").update(
        {"telegram_id": telegram_id}
    ).eq("id", attendee_id).execute()


def mark_checked_in(attendee_id: str) -> dict:
    res = _client().table("attendees").update({"checked_in": True}).eq("id", attendee_id).execute()
    return res.data[0]


def save_embedding(attendee_id: str, embedding: list[float]) -> None:
    """Store the pgvector embedding for an attendee."""
    _client().table("attendees").update({"embedding": embedding}).eq("id", attendee_id).execute()


def get_checked_in_attendees() -> list[dict]:
    res = _client().table("attendees").select("*").eq("checked_in", True).execute()
    return res.data or []


def get_all_attendees() -> list[dict]:
    res = _client().table("attendees").select("*").execute()
    return res.data or []



# ─────────────────────────────────────────────────────────────
#  SEMANTIC MATCHMAKING
# ─────────────────────────────────────────────────────────────

def find_matches(query_embedding: list[float], exclude_id: str, limit: int = 5) -> list[dict]:
    """
    Runs cosine similarity search via Supabase RPC (match_attendees function).
    Returns top-N most compatible checked-in attendees.
    """
    res = _client().rpc("match_attendees", {
        "query_embedding": query_embedding,
        "exclude_id": exclude_id,
        "match_count": limit,
    }).execute()
    return res.data or []


def record_match_interaction(attendee_a: str, attendee_b: str, action: str) -> None:
    """action: 'accept' | 'next' | 'pending'"""
    _client().table("match_interactions").insert({
        "attendee_a": attendee_a,
        "attendee_b": attendee_b,
        "action": action,
    }).execute()


# ─────────────────────────────────────────────────────────────
#  SOCIAL WALL
# ─────────────────────────────────────────────────────────────

def save_wall_photo(telegram_id: int, attendee_name: str, original_url: str, branded_url: str) -> dict:
    row = {
        "telegram_id": telegram_id,
        "attendee_name": attendee_name,
        "original_url": original_url,
        "branded_url": branded_url,
        "approved": True,
    }
    res = _client().table("wall_photos").insert(row).execute()
    return res.data[0]


# ─────────────────────────────────────────────────────────────
#  CERTIFICATES
# ─────────────────────────────────────────────────────────────

def save_certificate(attendee_id: str, cert_url: str, rank: str) -> dict:
    cert_id = str(uuid.uuid4())
    qr_data = f"{cert_id}"   # used for verify URL
    res = _client().table("certificates").insert({
        "id": cert_id,
        "attendee_id": attendee_id,
        "cert_url": cert_url,
        "qr_data": qr_data,
        "rank": rank,
    }).execute()
    return res.data[0]


def get_certificate(cert_id: str) -> dict | None:
    res = _client().table("certificates").select("*, attendees(name, email)").eq("id", cert_id).maybe_single().execute()
    if res.data:
        # Increment verified_count on each scan
        _client().table("certificates").update(
            {"verified_count": (res.data.get("verified_count", 0) + 1)}
        ).eq("id", cert_id).execute()
    return res.data


# ─────────────────────────────────────────────────────────────
#  FEEDBACK
# ─────────────────────────────────────────────────────────────

def save_feedback(attendee_id: str, message: str, sentiment: str = "") -> None:
    _client().table("feedback").insert({
        "attendee_id": attendee_id,
        "message": message,
        "sentiment": sentiment,
    }).execute()


def get_all_feedback() -> list[dict]:
    res = _client().table("feedback").select("*, attendees(name)").execute()
    return res.data or []


# ─────────────────────────────────────────────────────────────
#  COMPLAINTS — Help-Desk & Escalation
# ─────────────────────────────────────────────────────────────

def log_complaint(row: dict) -> dict:
    """
    INSERT a new complaint row.
    Expected keys: telegram_id, telegram_username, attendee_id (nullable),
                   category, severity, description, summary, location, status.
    Returns the created row (with UUID `id` and `created_at`).
    """
    res = _client().table("complaints").insert(row).execute()
    return res.data[0]


def update_complaint_status(
    complaint_id: str,
    status: str,
    resolved_by: int | None = None,
) -> None:
    """
    PATCH a complaint's status (open → resolved | escalated).
    `resolved_by` is the admin's Telegram numeric ID.
    """
    payload: dict = {"status": status}
    if resolved_by is not None:
        payload["resolved_by"] = resolved_by
    if status in ("resolved", "escalated"):
        from datetime import datetime, timezone
        payload["resolved_at"] = datetime.now(timezone.utc).isoformat()
    _client().table("complaints").update(payload).eq("id", complaint_id).execute()


def get_complaint(complaint_id: str) -> dict | None:
    """Fetch a single complaint row by UUID."""
    res = (
        _client()
        .table("complaints")
        .select("*, attendees(name, telegram_id)")
        .eq("id", complaint_id)
        .maybe_single()
        .execute()
    )
    return res.data
