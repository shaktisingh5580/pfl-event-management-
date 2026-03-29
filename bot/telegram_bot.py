"""
bot/telegram_bot.py
The central Telegram Bot — handles all phases of the event lifecycle.
All Supabase calls are wrapped in try/except so the bot works even
when the database is not yet configured.
"""
import asyncio
import io
import json
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID,
    EVENT_NAME, EVENT_DATE, EVENT_VENUE, OUTPUTS_DIR
)

# ── Safe Supabase imports — won't crash if DB not configured ─────────────────
def _safe_get_attendee_by_telegram(telegram_id):
    try:
        from tools.supabase_tool import get_attendee_by_telegram
        return get_attendee_by_telegram(telegram_id)
    except Exception:
        return None

def _safe_get_attendee_by_id(attendee_id):
    try:
        from tools.supabase_tool import get_attendee_by_id
        return get_attendee_by_id(attendee_id)
    except Exception:
        return None

def _safe_mark_checked_in(attendee_id):
    try:
        from tools.supabase_tool import mark_checked_in
        mark_checked_in(attendee_id)
        return True
    except Exception:
        return False

def _safe_save_feedback(attendee_id, message):
    try:
        from tools.supabase_tool import save_feedback
        save_feedback(attendee_id, message)
        return True
    except Exception:
        return False

def _safe_record_match(aid_a, aid_b, action):
    try:
        from tools.supabase_tool import record_match_interaction
        record_match_interaction(aid_a, aid_b, action)
    except Exception:
        pass

def _safe_log_complaint(row: dict):
    try:
        from tools.supabase_tool import log_complaint
        return log_complaint(row)
    except Exception:
        return None

def _safe_update_complaint(complaint_id: str, status: str, resolved_by: int = None):
    try:
        from tools.supabase_tool import update_complaint_status
        update_complaint_status(complaint_id, status, resolved_by)
    except Exception:
        pass

def _safe_get_complaint(complaint_id: str):
    try:
        from tools.supabase_tool import get_complaint
        return get_complaint(complaint_id)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def is_admin(update: Update) -> bool:
    return update.effective_user.id == TELEGRAM_ADMIN_CHAT_ID


async def send_typing(update: Update):
    await update.effective_chat.send_action("typing")


# ── Safe helpers for new functions ──────────────────────────────────────────

def _safe_get_attendee_by_username(username: str):
    try:
        from tools.supabase_tool import get_attendee_by_username
        return get_attendee_by_username(username)
    except Exception:
        return None

def _safe_update_telegram_id(attendee_id: str, telegram_id: int):
    try:
        from tools.supabase_tool import update_telegram_id
        update_telegram_id(attendee_id, telegram_id)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
#  /start — Welcome
# ═══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    tg_username = (user.username or "").strip()

    try:
        # ── Case 1: Already linked by numeric telegram_id (returning user) ──
        attendee = _safe_get_attendee_by_telegram(tg_id)

        if not attendee and tg_username:
            # ── Case 2: Website registrant — match by @username, then link ──
            attendee = _safe_get_attendee_by_username(tg_username)
            if attendee:
                # Save their numeric telegram_id so future lookups are instant
                _safe_update_telegram_id(attendee["id"], tg_id)
                print(f"[Bot] Linked @{tg_username} (tg_id={tg_id}) → attendee {attendee['id']}")

        if attendee:
            name = attendee.get("name", user.first_name)

            # ── Generate + send QR code as image ────────────────────────────
            qr_img_bio = None
            try:
                from tools.qr_tool import generate_ticket_qr
                import io as _io
                from PIL import Image as _PILImage

                qr_path = generate_ticket_qr(attendee["id"], name)
                img = _PILImage.open(str(qr_path))
                qr_img_bio = _io.BytesIO()
                img.save(qr_img_bio, format="PNG")
                qr_img_bio.seek(0)
            except Exception as e:
                print(f"[Bot] QR gen error: {e}")

            # ── Welcome message ──────────────────────────────────────────────
            college    = attendee.get("college", "")
            department = attendee.get("department", "")
            year       = attendee.get("year_of_study", "")
            seat       = attendee.get("seat", "TBA")
            coord      = attendee.get("coordinator", "Event Staff")

            profile_line = ""
            if college:
                profile_line = f"🏫 {college}"
                if department:
                    profile_line += f" · {department}"
                if year:
                    profile_line += f" · {year}"

            welcome_msg = (
                f"🎉 *Welcome to {EVENT_NAME}, {name}!* 🎉\n\n"
                f"You're officially registered! Here's your info:\n\n"
                + (f"{profile_line}\n" if profile_line else "")
                + f"💺 Seat: *{seat}*\n"
                  f"👤 Coordinator: *{coord}*\n\n"
                  f"📲 *What I can do for you:*\n"
                  f"  • 🤝 AI networking — I'll match you with compatible people\n"
                  f"  • 📸 Send a selfie → appear on the big live screen!\n"
                  f"  • 🎓 Receive your certificate after the event\n"
                  f"  • 💬 Ask me anything about the event\n"
                  f"  • /complaint — Report an issue instantly\n"
                  f"  • /feedback — Share your thoughts\n\n"
                  f"📍 *Date & Venue:* {EVENT_DATE} · {EVENT_VENUE}\n"
                  f"🗺️ Show the QR code below at the gate for check-in!"
            )

            if qr_img_bio:
                await update.message.reply_photo(
                    photo=qr_img_bio,
                    caption=welcome_msg,
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(welcome_msg, parse_mode="Markdown")

        else:
            # ── Case 3: Completely new user — not registered via website ──
            await update.message.reply_text(
                f"👋 Welcome to *{EVENT_NAME}* bot!\n\n"
                f"I don't see you in the attendee list yet.\n\n"
                f"📝 *Register first* at the event website, then come back here "
                f"and type /start — I'll send you your QR ticket!\n\n"
                f"Already registered? Make sure you used the same Telegram username "
                f"(*@{tg_username}*) in the website form.\n\n"
                f"Commands:\n"
                f"  /checkin — Gate check-in (staff use)\n"
                f"  /feedback — Share event feedback\n"
                f"  💬 Or ask me anything about {EVENT_NAME}!",
                parse_mode="Markdown",
            )

    except Exception as e:
        print(f"[Bot] /start error: {e}")
        await update.message.reply_text(
            f"👋 Welcome to *{EVENT_NAME}*! I'm your event assistant.\n"
            f"Ask me anything or use /checkin to check in.",
            parse_mode="Markdown",
        )



# ═══════════════════════════════════════════════════════════
#  /checkin — Gate QR Check-In
# ═══════════════════════════════════════════════════════════

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /checkin <attendee_id>")
        return

    attendee_id = context.args[0].strip()

    try:
        attendee = _safe_get_attendee_by_id(attendee_id)

        if not attendee:
            await update.message.reply_text(
                "❌ QR code not recognized.\n"
                "Please show this error to event staff."
            )
            return

        if attendee.get("checked_in"):
            await update.message.reply_text(
                f"⚠️ {attendee['name']} is already checked in!"
            )
            return

        _safe_mark_checked_in(attendee_id)

        # Build dynamic fields info if available
        dyn_info = ""
        dyn_fields = attendee.get("dynamic_fields")
        if dyn_fields and isinstance(dyn_fields, dict):
            for key, val in dyn_fields.items():
                label = key.replace("_", " ").title()
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val if v)
                if val:
                    dyn_info += f"📋 {label}: *{val}*\n"

        await update.message.reply_text(
            f"✅ *Checked in: {attendee['name']}*\n\n"
            f"📍 Head to: *{attendee.get('seat', 'Reception desk')}*\n"
            f"👤 Your coordinator: *{attendee.get('coordinator', 'Event Staff')}*\n"
            + (f"\n{dyn_info}" if dyn_info else "")
            + f"\n🎉 Enjoy {EVENT_NAME}!",
            parse_mode="Markdown",
        )

        # Background: generate matchmaking embedding if skills/interests exist
        try:
            skills = attendee.get("skills", "")
            interests = attendee.get("interests", "")
            goals = attendee.get("goals", "")
            if skills or interests or goals:
                from agents.matchmaking_agent import embed_and_store
                embed_and_store(attendee_id, skills or "", interests or "", goals or "")
                print(f"[Bot] Matchmaking embedding created for {attendee['name']}")
        except Exception as e:
            print(f"[Bot] Matchmaking embed skipped: {e}")

        # Background: send welcome PDF via DM
        try:
            import json as _json
            from agents.comms_agent import generate_welcome_pdf
            sched_path = OUTPUTS_DIR / "schedule.json"
            schedule = []
            if sched_path.exists():
                data = _json.loads(sched_path.read_text(encoding="utf-8"))
                # The schedule.json created by the architect has it nested as data['plan']['plan']
                plan = data.get("plan", {}).get("plan", {})
                if not plan:
                    plan = data.get("plan", {})
                schedule = plan.get("schedule", [])
            pdf_path = generate_welcome_pdf(attendee, schedule)
            if pdf_path and pdf_path.exists() and attendee.get("telegram_id"):
                await context.bot.send_document(
                    chat_id=attendee["telegram_id"],
                    document=open(str(pdf_path), "rb"),
                    caption=f"🎫 Your personalized welcome ticket for {EVENT_NAME}!",
                )
                print(f"[Bot] Welcome PDF sent to {attendee['name']}")
        except Exception as e:
            print(f"[Bot] Welcome PDF skipped: {e}")

    except Exception as e:
        await update.message.reply_text(
            "⚠️ Check-in system temporarily unavailable. Please see event staff."
        )


# ═══════════════════════════════════════════════════════════
#  Photo Handler — Social Wall Pipeline
# ═══════════════════════════════════════════════════════════

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        attendee = _safe_get_attendee_by_telegram(user.id)
        sender_name = attendee["name"] if attendee else user.full_name

        await send_typing(update)
        await update.message.reply_text(
            "📸 Got your selfie! Running safety check... ⏳"
        )

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        bio = io.BytesIO()
        await file.download_to_memory(bio)
        image_bytes = bio.getvalue()

        # Stage 2: AI Moderation
        try:
            from agents.social_wall_agent import ai_moderate_image, send_for_admin_approval
            is_safe, reason = await ai_moderate_image(image_bytes)
        except Exception:
            is_safe, reason = True, "Auto-moderation unavailable"

        if not is_safe:
            await update.message.reply_text(
                f"❌ Your photo couldn't be added to the wall.\n"
                f"Reason: {reason}\n\nPlease try a different photo!"
            )
            return

        # Stage 3: Send to admin for approval
        try:
            from agents.social_wall_agent import send_for_admin_approval
            await send_for_admin_approval(
                bot=context.bot,
                image_bytes=image_bytes,
                sender_name=sender_name,
                sender_telegram_id=user.id,
                temp_file_id=photo.file_id,
            )
            await update.message.reply_text(
                "✅ Safety check passed! Your photo is pending admin approval.\n"
                "🎥 Watch the big screen — you might appear soon!"
            )
        except Exception:
            await update.message.reply_text(
                "📸 Photo received! Admin will review it shortly."
            )

    except Exception as e:
        await update.message.reply_text(
            "📸 Got your photo! It's being processed for the wall."
        )


# ═══════════════════════════════════════════════════════════
#  SMART MESSAGE ROUTING — Intent Classification
# ═══════════════════════════════════════════════════════════

# Cache for ambiguous clarification flow (text too long for callback_data)
_intent_cache: dict[str, dict] = {}

# Greetings detected without any LLM call (instant + saves tokens)
_GREETING_STARTS = (
    "hi", "hey", "hello", "hiya", "howdy", "yo ", "sup",
    "good morning", "good afternoon", "good evening",
    "gm ", "gn ", "namaste", "help", "start", "menu",
    "what can you", "what do you", "who are you", "what are you",
)

def _is_greeting(text: str) -> bool:
    t = text.strip().lower()
    if len(t) <= 3 and t in {"hi", "hey", "yo", "gm", "gn"}:
        return True
    return any(t.startswith(kw) for kw in _GREETING_STARTS)


_INTENT_PROMPT = """You are the AI brain of a Telegram event assistant bot.
Classify the user message into exactly one intent label.
Reply ONLY with a compact JSON — no markdown, no extra text.

{"intent": "<label>", "confidence": <0.0-1.0>}

Intent labels:
  "complaint"  - reporting a problem, broken item, missing resource, grievance
  "feedback"   - sharing opinion, rating, suggestion, compliment, general experience
  "greeting"   - hi/hello, asking what the bot does, starting a conversation
  "question"   - asking for event info, schedule, venue, rules, team details
  "ambiguous"  - genuinely unclear: could be complaint OR feedback

Low confidence (<0.65) on complaint/feedback should become "ambiguous".
"""

async def _classify_intent(text: str) -> tuple[str, float]:
    """LLM intent classifier. Returns (label, confidence). Fallback: 'question'."""
    try:
        import json, re
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
        from openai import OpenAI
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        r = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_PROMPT},
                {"role": "user",   "content": text[:300]},
            ],
            max_tokens=30,
            temperature=0.1,
        )
        raw = r.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        parsed = json.loads(raw)
        intent = parsed.get("intent", "question")
        confidence = float(parsed.get("confidence", 0.5))
        if intent not in {"complaint", "feedback", "greeting", "question", "ambiguous"}:
            intent = "question"
        return intent, confidence
    except Exception as e:
        print(f"[Bot] Intent classify error: {e}")
        return "question", 0.5



def _msg_of(src):
    """Return the sendable message object from either an Update or a CallbackQuery."""
    # Update has .message; CallbackQuery has .message directly
    if hasattr(src, 'message') and src.message is not None:
        return src.message
    # Fallback for Update that has effective_message
    if hasattr(src, 'effective_message') and src.effective_message:
        return src.effective_message
    return src.message  # will raise naturally if something unexpected is passed


async def _send_bot_overview(src):
    """Quick welcome card shown on greetings and first messages."""
    msg = _msg_of(src)
    keyboard = [[InlineKeyboardButton("📖 Full Bot Guide", callback_data="show_guide")]]
    await msg.reply_text(
        f"👋 Hi! I'm the *{EVENT_NAME}* AI Assistant.\n\n"
        f"Here's what I can do:\n\n"
        f"🎟 /start \u2014 QR ticket + seat & coordinator info\n"
        f"🚨 /complaint \u2014 Report any issue (AI-categorized)\n"
        f"💬 /feedback \u2014 Share your thoughts\n"
        f"📸 Send a selfie \u2192 appear on the live wall!\n"
        f"❓ Ask me anything about the event\n\n"
        f"Just *type naturally* \u2014 I'll detect if it's a complaint, feedback, or question!\n\n"
        f"👇 Tap for the full feature guide:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _route_as_complaint(src, context: ContextTypes.DEFAULT_TYPE, text: str, auto: bool = True):
    """Run the full complaint pipeline for an auto-detected or confirmed complaint."""
    msg = _msg_of(src)
    user = src.effective_user if hasattr(src, 'effective_user') else src.from_user
    tg_id = user.id
    tg_username = (user.username or "").strip()

    attendee_id = None
    try:
        a = _safe_get_attendee_by_telegram(tg_id)
        if a:
            attendee_id = a["id"]
    except Exception:
        pass

    prefix = "🤖 Detected as a complaint \u2014 logged automatically.\n\n" if auto else ""

    try:
        from agents.complaint_agent import categorize_and_log_complaint
        complaint_row = await categorize_and_log_complaint(
            text=text, telegram_id=tg_id,
            telegram_username=tg_username, attendee_id=attendee_id,
        )
    except Exception as e:
        print(f"[Bot] Auto-complaint agent error: {e}")
        complaint_row = {
            "id": None, "category": "Other", "severity": "medium",
            "summary": text[:80], "location": "", "description": text,
        }

    cid      = complaint_row.get("id") or "unknown"
    category = complaint_row.get("category", "Other")
    severity = complaint_row.get("severity", "medium")
    summary  = complaint_row.get("summary", text[:80])
    location = complaint_row.get("location", "") or ""
    sev_emoji = _SEV_EMOJI.get(severity, "🟠")
    cat_emoji = _CAT_EMOJI.get(category, "📌")
    short_id  = str(cid)[:8].upper() if cid != "unknown" else "PENDING"

    _complaint_cache[short_id] = {
        "cid": cid, "user_tg_id": tg_id, "category": category,
        "severity": severity, "summary": summary, "location": location,
    }

    reply_msg = _msg_of(src)
    await reply_msg.reply_text(
        prefix
        + f"{sev_emoji} Complaint logged!\n"
        + f"{cat_emoji} Category: {category} | Severity: {severity.capitalize()}\n"
        + (f"📍 Location: {location}\n" if location else "")
        + f"🆔 Ref: #{short_id}\n\nOur team has been notified. We'll get back to you shortly!"
    )

    # Admin alert
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        user_tag = f"@{tg_username}" if tg_username else f"tg:{tg_id}"
        header = "‼️ EMERGENCY ALERT ‼️" if severity == "emergency" else f"{sev_emoji} NEW COMPLAINT"
        alert_text = (
            f"{header}\n"
            f"{cat_emoji} {category} \u2014 Severity: {severity.upper()}\n\n"
            f"👤 Reporter: {user_tag} ({tg_id})\n"
            + (f"📍 Location: {location}\n" if location else "")
            + f'📝 "{summary}"\n'
              f"🆔 Complaint ID: {cid}\n"
              f"⏰ {ts}"
        )
        wa_text = (
            f"ESCALATION+ALERT:+{category.upper()}+complaint."
            + (f"+Location:+{location.replace(' ', '+')}.+" if location else "+")
            + f"Issue:+{summary.replace(' ', '+')}.+Ref:+%23{short_id}"
        )
        admin_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Resolved",  callback_data=f"complaint_resolve|{short_id}"),
                InlineKeyboardButton("🔺 Escalate",  callback_data=f"complaint_escalate|{short_id}"),
            ],
            [InlineKeyboardButton("📲 WhatsApp Coordinator", url=f"https://wa.me/?text={wa_text}")],
        ])
        admin_msg = await context.bot.send_message(
            chat_id=TELEGRAM_ADMIN_CHAT_ID,
            text=alert_text,
            reply_markup=admin_keyboard,
        )
        print(f"[Bot] Auto-complaint admin alert sent (msg_id={admin_msg.message_id})")
        if cid != "unknown":
            try:
                from tools.supabase_tool import _client as _sb
                _sb().table("complaints").update(
                    {"admin_message_id": admin_msg.message_id}
                ).eq("id", cid).execute()
            except Exception:
                pass
    except Exception as e:
        import traceback
        print(f"[Bot] Auto-complaint admin alert failed: {e}")
        traceback.print_exc()


async def _route_as_feedback(src, context: ContextTypes.DEFAULT_TYPE, text: str, auto: bool = True):
    """Log text as feedback and acknowledge."""
    msg = _msg_of(src)
    user = src.effective_user if hasattr(src, 'effective_user') else src.from_user
    try:
        attendee = _safe_get_attendee_by_telegram(user.id)
        aid = attendee["id"] if attendee else None
        _safe_save_feedback(aid, text)
    except Exception:
        pass
    prefix = "🤖 Detected as feedback \u2014 logged.\n\n" if auto else ""
    await msg.reply_text(
        prefix + "🙏 Thank you for your feedback! It helps us make the event even better."
    )


async def _ask_clarify(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Ask user whether ambiguous text is a complaint, feedback, or question."""
    import uuid
    sid = str(uuid.uuid4())[:8].upper()
    _intent_cache[sid] = {
        "text": text,
        "tg_id": update.effective_user.id,
        "username": (update.effective_user.username or "").strip(),
    }
    preview = f'"{text[:80]}{"..." if len(text) > 80 else ""}"'
    keyboard = [
        [
            InlineKeyboardButton("🚨 It's a Complaint", callback_data=f"clarify_c|{sid}"),
            InlineKeyboardButton("💬 It's Feedback",    callback_data=f"clarify_f|{sid}"),
        ],
        [InlineKeyboardButton("❓ Just a Question",     callback_data=f"clarify_q|{sid}")],
    ]
    await update.message.reply_text(
        f"🤔 I'm not sure how to classify this:\n{preview}\n\nHow should I treat it?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _rag_answer(src, user_msg: str):
    """Pass to RAG concierge for event questions."""
    msg = _msg_of(src)
    try:
        from agents.concierge_agent import answer_question
        answer = await answer_question(user_msg)
    except Exception:
        try:
            from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
            from openai import OpenAI
            client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            r = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": f"You are the helpful AI assistant for {EVENT_NAME}. Answer event questions helpfully and briefly."},
                    {"role": "user",   "content": user_msg},
                ],
                max_tokens=200,
            )
            answer = r.choices[0].message.content.strip()
        except Exception:
            answer = f"🤔 I couldn't find info on that. Please ask event staff or check the {EVENT_NAME} rulebook!"
    await msg.reply_text(answer)


# ── Smart message router ──────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text.strip()

    # 1. Instant greeting check — zero LLM cost
    if _is_greeting(user_msg):
        await _send_bot_overview(update)
        return

    await send_typing(update)

    # 2. LLM intent classification
    intent, confidence = await _classify_intent(user_msg)
    print(f"[Bot] Intent={intent} ({confidence:.2f}): {user_msg[:50]}")

    # 3. Route by intent
    if intent == "greeting":
        await _send_bot_overview(update)

    elif intent == "complaint" and confidence >= 0.70:
        await _route_as_complaint(update, context, user_msg, auto=True)

    elif intent == "feedback" and confidence >= 0.70:
        await _route_as_feedback(update, context, user_msg, auto=True)

    elif intent == "ambiguous" or (
        intent in ("complaint", "feedback") and confidence < 0.70
    ):
        await _ask_clarify(update, context, user_msg)

    else:
        # "question" or uncertain → RAG concierge
        await _rag_answer(update, user_msg)


# ═══════════════════════════════════════════════════════════
#  /complaint — Help-Desk & Escalation
# ═══════════════════════════════════════════════════════════

# Emoji severity indicators used in admin alerts
_SEV_EMOJI = {"low": "🟡", "medium": "🟠", "high": "🔴", "emergency": "‼️"}
_CAT_EMOJI = {
    "Technical": "💻", "Logistics": "📦",
    "Facilities": "🏢", "Emergency": "‼️", "Other": "📌"
}

# Callback data is limited to 64 bytes by Telegram.
# We store {short_id -> full complaint info} in memory and only put short_id in buttons.
_complaint_cache: dict[str, dict] = {}


def _esc(text: str) -> str:
    """Escape chars that break Telegram Markdown v1 (used in user messages)."""
    return str(text).replace("_", "\_").replace("`", "\`").replace("*", "\*")


async def complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    tg_username = (user.username or "").strip()

    if not context.args:
        # Show usage + quick-pick category buttons
        keyboard = [
            [
                InlineKeyboardButton("💻 Technical",  callback_data="complaint_pick|Technical"),
                InlineKeyboardButton("📦 Logistics",  callback_data="complaint_pick|Logistics"),
            ],
            [
                InlineKeyboardButton("🏢 Facilities", callback_data="complaint_pick|Facilities"),
                InlineKeyboardButton("‼️ Emergency",  callback_data="complaint_pick|Emergency"),
            ],
            [
                InlineKeyboardButton("📌 Other",      callback_data="complaint_pick|Other"),
            ],
        ]
        await update.message.reply_text(
            "🚨 *Report an Issue*\n\n"
            "Type your complaint directly:\n"
            "`/complaint <describe your issue here>`\n\n"
            "*Example:*\n"
            "`/complaint AC is broken in Hall B, it's very hot`\n\n"
            "Or tap a category below to get started:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    text = " ".join(context.args).strip()
    await send_typing(update)

    # Look up attendee (for linking)
    attendee_id = None
    try:
        attendee = _safe_get_attendee_by_telegram(tg_id)
        if attendee:
            attendee_id = attendee["id"]
    except Exception:
        pass

    # AI categorization + DB log
    try:
        from agents.complaint_agent import categorize_and_log_complaint
        complaint_row = await categorize_and_log_complaint(
            text=text,
            telegram_id=tg_id,
            telegram_username=tg_username,
            attendee_id=attendee_id,
        )
    except Exception as e:
        import traceback
        print(f"[Bot] complaint agent error: {e}")
        traceback.print_exc()
        complaint_row = {
            "id": None, "category": "Other", "severity": "medium",
            "summary": text[:80], "location": "", "description": text,
        }

    cid      = complaint_row.get("id") or "unknown"
    category = complaint_row.get("category", "Other")
    severity = complaint_row.get("severity", "medium")
    summary  = complaint_row.get("summary", text[:80])
    location = complaint_row.get("location", "") or ""
    sev_emoji = _SEV_EMOJI.get(severity, "🟠")
    cat_emoji = _CAT_EMOJI.get(category, "📌")

    # ── Confirm to user ─────────────────────────────────────
    short_id = str(cid)[:8].upper() if cid != "unknown" else "PENDING"

    # Cache complaint data so callback buttons only need the short_id (≤64 byte limit)
    _complaint_cache[short_id] = {
        "cid":         cid,
        "user_tg_id":  tg_id,
        "category":    category,
        "severity":    severity,
        "summary":     summary,
        "location":    location,
    }

    await update.message.reply_text(
        f"{sev_emoji} Complaint logged!\n\n"
        f"{cat_emoji} Category: {category}\n"
        f"⚡ Severity: {severity.capitalize()}\n"
        + (f"📍 Location: {location}\n" if location else "")
        + f"🆔 Ref: #{short_id}\n\n"
          f"Our team has been notified. We'll get back to you shortly!",
    )

    # ── Admin alert ──────────────────────────────────────────
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        user_tag = f"@{tg_username}" if tg_username else f"tg:{tg_id}"

        alert_header = "‼️ EMERGENCY ALERT ‼️" if severity == "emergency" else f"{sev_emoji} NEW COMPLAINT"
        # Use plain text for admin alert — avoids Markdown parse errors from LLM-generated content
        alert_text = (
            f"{alert_header}\n"
            f"{cat_emoji} {category} — Severity: {severity.upper()}\n\n"
            f"👤 Reporter: {user_tag} ({tg_id})\n"
            + (f"📍 Location: {location}\n" if location else "")
            + f'📝 "{summary}"\n'
              f"🆔 Complaint ID: {cid}\n"
              f"⏰ {ts}"
        )

        # callback_data max = 64 bytes; use short_id only (26-27 bytes)
        resolve_data  = f"complaint_resolve|{short_id}"    # 26 bytes max
        escalate_data = f"complaint_escalate|{short_id}"   # 27 bytes max
        wa_text = (
            f"ESCALATION+ALERT:+{category.upper()}+complaint+at+{EVENT_VENUE.replace(' ','+')}.+"
            f"Issue:+{summary.replace(' ','+')}.+Reporter:+{user_tag}.+Ref:+{short_id}"
        )
        wa_url = f"https://wa.me/?text={wa_text}"

        admin_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Resolved",   callback_data=resolve_data),
                InlineKeyboardButton("🔺 Escalate",   callback_data=escalate_data),
            ],
            [
                InlineKeyboardButton("📲 WhatsApp Coordinator", url=wa_url),
            ],
        ])

        print(f"[Bot] Sending admin complaint alert to chat_id={TELEGRAM_ADMIN_CHAT_ID}")
        admin_msg = await context.bot.send_message(
            chat_id=TELEGRAM_ADMIN_CHAT_ID,
            text=alert_text,
            reply_markup=admin_keyboard,
        )
        print(f"[Bot] Admin alert sent OK (msg_id={admin_msg.message_id})")

        # Persist the admin message ID so we can edit it later on resolve/escalate
        if cid != "unknown" and admin_msg:
            try:
                from tools.supabase_tool import _client as _sb
                _sb().table("complaints").update(
                    {"admin_message_id": admin_msg.message_id}
                ).eq("id", cid).execute()
            except Exception:
                pass

    except Exception as e:
        import traceback
        print(f"[Bot] Admin complaint alert failed: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════
#  /feedback — Post-event feedback
# ═══════════════════════════════════════════════════════════

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📝 Share your feedback!\n"
            "Type: /feedback <your message>\n"
            "Example: /feedback The event was amazing!"
        )
        return

    msg = " ".join(context.args)
    try:
        attendee = _safe_get_attendee_by_telegram(update.effective_user.id)
        aid = attendee["id"] if attendee else None
        _safe_save_feedback(aid, msg)
    except Exception:
        pass

    await update.message.reply_text(
        "🙏 Thank you for your feedback! It helps us make the next event even better."
    )


# ═══════════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════

async def run_matchmaking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    meeting_point = " ".join(context.args) if context.args else "the Networking Zone"
    await update.message.reply_text(f"🤝 Starting matchmaking blast... Meeting point: {meeting_point}")
    try:
        from agents.matchmaking_agent import run_matchmaking_blast
        count = await run_matchmaking_blast(context.bot, meeting_point)
        await update.message.reply_text(f"✅ Sent {count} match introductions!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Matchmaking error: {str(e)[:100]}\nMake sure Supabase is configured.")


async def blast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /blast <message>")
        return
    msg = " ".join(context.args)
    try:
        from agents.comms_agent import send_group_blast
        await send_group_blast(context.bot, msg)
        await update.message.reply_text("📢 Blast sent!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Blast error: {str(e)[:100]}")


async def dm_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /dm <template message>\n"
            "Variables: {{ name }}, {{ seat }}, {{ coordinator }}"
        )
        return
    template = " ".join(context.args)
    try:
        from agents.comms_agent import send_personalized_dm
        count = await send_personalized_dm(context.bot, template)
        await update.message.reply_text(f"✅ Sent {count} personalized DMs!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ DM error: {str(e)[:100]}")


async def generate_certs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("🎓 Generating certificates for all checked-in attendees...")
    try:
        from agents.certificate_agent import run_all_certificates
        paths = run_all_certificates()
        await update.message.reply_text(f"✅ Generated {len(paths)} certificates!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Certificate error: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════
#  INLINE BUTTON CALLBACKS
# ═══════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        # ── Social Wall: Approve ────────────────────────────────
        if data.startswith("wall_approve|"):
            _, telegram_id, file_id, sender_name = data.split("|", 3)
            telegram_id = int(telegram_id)
            file = await context.bot.get_file(file_id)
            bio = io.BytesIO()
            await file.download_to_memory(bio)
            try:
                from agents.social_wall_agent import apply_overlay_and_push
                branded_url = apply_overlay_and_push(bio.getvalue(), sender_name, telegram_id)
                await query.edit_message_caption(f"✅ Approved & posted to wall!\n📸 {sender_name}")
            except Exception:
                await query.edit_message_caption(f"✅ Approved — {sender_name}")
            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"🎉 {sender_name}, your photo is on the big screen! 📺"
            )

        # ── Social Wall: Reject ─────────────────────────────────
        elif data.startswith("wall_reject|"):
            _, telegram_id, file_id, sender_name = data.split("|", 3)
            await query.edit_message_caption(f"❌ Rejected — {sender_name}")
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text="Your photo wasn't approved for the wall this time. Please try a different one!"
            )

        # ── Matchmaking: Accept ─────────────────────────────────
        elif data.startswith("match_accept|"):
            _, attendee_a_id, attendee_b_id = data.split("|")
            a = _safe_get_attendee_by_id(attendee_a_id)
            b = _safe_get_attendee_by_id(attendee_b_id)
            _safe_record_match(attendee_a_id, attendee_b_id, "accept")
            if a and b:
                if b.get("telegram_id"):
                    await context.bot.send_message(
                        chat_id=b["telegram_id"],
                        text=f"🤝 *{a['name']}* accepted your introduction!\n"
                             f"📧 Email: {a.get('email', 'N/A')}",
                        parse_mode="Markdown",
                    )
                await query.edit_message_reply_markup(None)
                await context.bot.send_message(
                    chat_id=a["telegram_id"],
                    text=f"✅ Connection made with *{b['name']}*!\n"
                         f"📧 Their email: {b.get('email', 'N/A')}",
                    parse_mode="Markdown",
                )

        # ── Matchmaking: Next ───────────────────────────────────
        elif data.startswith("match_next|"):
            _, attendee_a_id, attendee_b_id = data.split("|")
            _safe_record_match(attendee_a_id, attendee_b_id, "next")
            await query.edit_message_reply_markup(None)
            await query.edit_message_text("⏭ Looking for your next match... Check back in a moment!")

        # ── Bot Guide ────────────────────────────────────────────
        elif data == "show_guide":
            guide = (
                f"📖 {EVENT_NAME} Bot — Complete Guide\n\n"
                f"COMMANDS\n"
                f"• /start — Welcome + QR ticket + your seat & coordinator\n"
                f"• /complaint <issue> — AI categorizes & instantly alerts admin\n"
                f"• /feedback <text> — Post-event feedback\n"
                f"• /checkin <id> — Staff gate check-in\n\n"
                f"SMART FEATURES\n"
                f"• Just type your problem — I'll auto-detect if it's a complaint\n"
                f"• Unsure? I'll ask you whether it's a complaint, feedback, or question\n"
                f"• Send a photo → live Social Wall (after admin approval)\n"
                f"• Type your skills/interests → AI finds you a networking match\n\n"
                f"COMPLAINT CATEGORIES\n"
                f"• 💻 Technical — WiFi, laptops, coding judge\n"
                f"• 📦 Logistics — food, badges, registration, bus\n"
                f"• 🏢 Facilities — AC, lights, washrooms, seating\n"
                f"• ‼️ Emergency — medical, safety, fire\n\n"
                f"ADMIN ACTIONS (restricted)\n"
                f"• /blast — Message all attendees\n"
                f"• /dm — Personalized DM blast\n"
                f"• /gen_certs — Generate certificates\n"
                f"• /run_matchmaking — AI networking blast\n\n"
                f"TIPS\n"
                f"• Register on the website first, then /start to get your QR ticket\n"
                f"• Type 'emergency' in a complaint for instant high-priority alert\n"
                f"• All complaints are tracked with a Ref# so you can follow up"
            )
            await query.edit_message_text(guide)

        # ── Clarification: User confirms as Complaint ────────────
        elif data.startswith("clarify_c|"):
            sid = data.split("|")[1]
            cached = _intent_cache.get(sid, {})
            text = cached.get("text", "")
            if text:
                await query.edit_message_text("🚨 Got it — logging as a complaint...")
                await _route_as_complaint(query, context, text, auto=False)
            else:
                await query.edit_message_text("⚠️ Session expired. Please retype your message.")

        # ── Clarification: User confirms as Feedback ─────────────
        elif data.startswith("clarify_f|"):
            sid = data.split("|")[1]
            cached = _intent_cache.get(sid, {})
            text = cached.get("text", "")
            if text:
                await query.edit_message_text("💬 Got it — logging as feedback...")
                await _route_as_feedback(query, context, text, auto=False)
            else:
                await query.edit_message_text("⚠️ Session expired. Please retype your message.")

        # ── Clarification: User confirms as Question ──────────────
        elif data.startswith("clarify_q|"):
            sid = data.split("|")[1]
            cached = _intent_cache.get(sid, {})
            text = cached.get("text", "")
            if text:
                await query.edit_message_text("❓ Got it — searching for an answer...")
                await _rag_answer(query, text)
            else:
                await query.edit_message_text("⚠️ Session expired. Please retype your message.")

        # ── Complaint: Category quick-pick ──────────────────────
        elif data.startswith("complaint_pick|"):

            _, category = data.split("|", 1)
            cat_emoji = _CAT_EMOJI.get(category, "📌")
            await query.edit_message_text(
                f"{cat_emoji} *{category} Complaint*\n\n"
                f"Please describe your issue by typing:\n"
                f"`/complaint <your issue here>`\n\n"
                f"*Example:* `/complaint {category} issue — <details>`",
                parse_mode="Markdown",
            )

        # ── Complaint: Admin Resolve ────────────────────────────
        elif data.startswith("complaint_resolve|"):
            short_id = data.split("|")[1]                      # e.g. "ABCD1234"
            cached   = _complaint_cache.get(short_id, {})
            cid        = cached.get("cid", short_id)
            user_tg_id = cached.get("user_tg_id")
            admin_id   = query.from_user.id

            _safe_update_complaint(cid, "resolved", admin_id)

            # Edit admin message to resolved state
            try:
                old_lines = (query.message.text or "").split("\n")
                await query.edit_message_text(
                    f"✅ RESOLVED by admin\n"
                    f"🆔 Ref: #{short_id}\n"
                    + "\n".join(old_lines[1:4]),
                )
            except Exception:
                await query.edit_message_reply_markup(None)

            # DM the student
            if user_tg_id:
                try:
                    await context.bot.send_message(
                        chat_id=user_tg_id,
                        text=f"✅ Your complaint (#{short_id}) has been resolved!\n"
                             f"If the issue persists, please report again or speak to event staff.",
                    )
                except Exception as e:
                    print(f"[Bot] Could not DM student: {e}")

        # ── Complaint: Admin Escalate ───────────────────────────
        elif data.startswith("complaint_escalate|"):
            short_id = data.split("|")[1]
            cached   = _complaint_cache.get(short_id, {})
            cid        = cached.get("cid", short_id)
            user_tg_id = cached.get("user_tg_id")
            category   = cached.get("category", "Other")
            summary    = cached.get("summary", "")
            location   = cached.get("location", "")
            admin_id   = query.from_user.id
            cat_emoji  = _CAT_EMOJI.get(category, "📌")

            _safe_update_complaint(cid, "escalated", admin_id)

            # Build WhatsApp deep-link
            wa_parts = [f"ESCALATION+ALERT:+{category.upper()}+complaint."]
            if location:
                wa_parts.append(f"+Location:+{location.replace(' ', '+')}.")
            if summary:
                wa_parts.append(f"+Issue:+{summary.replace(' ', '+')}.")
            wa_parts.append(f"+Ref:+%23{short_id}")
            wa_url = "https://wa.me/?text=" + "".join(wa_parts)

            # Edit admin message
            try:
                old_lines = (query.message.text or "").split("\n")
                await query.edit_message_text(
                    f"🔺 ESCALATED by admin\n"
                    f"🆔 Ref: #{short_id}\n"
                    + "\n".join(old_lines[1:4]),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📲 Open WhatsApp", url=wa_url)]
                    ]),
                )
            except Exception:
                await query.edit_message_reply_markup(
                    InlineKeyboardMarkup([[InlineKeyboardButton("📲 Open WhatsApp", url=wa_url)]])
                )

            # DM the student
            if user_tg_id:
                try:
                    await context.bot.send_message(
                        chat_id=user_tg_id,
                        text=f"🔺 Your complaint (#{short_id}) has been escalated.\n"
                             f"A ground coordinator has been notified and will reach you shortly.",
                    )
                except Exception as e:
                    print(f"[Bot] Could not DM student on escalate: {e}")

    except Exception as e:
        print(f"[Bot] Callback error: {e}")


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(CommandHandler("complaint", complaint))

    # Admin commands
    app.add_handler(CommandHandler("run_matchmaking", run_matchmaking))
    app.add_handler(CommandHandler("blast", blast))
    app.add_handler(CommandHandler("dm", dm_all))
    app.add_handler(CommandHandler("gen_certs", generate_certs))

    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Auto-start scheduler if schedule exists and event is today
    try:
        import json as _json
        from datetime import date as _date
        from config import EVENT_DATE as _evt_date
        sched_path = OUTPUTS_DIR / "schedule.json"
        if sched_path.exists():
            today = _date.today().isoformat()
            if _evt_date and today == _evt_date:
                from agents.scheduler_agent import set_bot, start_scheduler
                set_bot(app.bot)
                result = start_scheduler(bot=app.bot)
                print(f"[Bot] Auto-started scheduler: {result}")
            else:
                print(f"[Bot] Scheduler not auto-started (event date {_evt_date} ≠ today {today})")
    except Exception as e:
        print(f"[Bot] Scheduler auto-start skipped: {e}")

    print(f"[Bot] {EVENT_NAME} Bot is running... Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
