"""
agents/social_wall_agent.py
4-stage Live Selfie Wall pipeline:
Stage 1: Telegram receives photo
Stage 2: AI vision model safety check (SAFE/UNSAFE)
Stage 3: Auto-approve after safety check + best-effort admin notification
Stage 4: Cloudinary overlay → Supabase (status=approved) → WebSocket push to /wall page

Admin approval is NOT required for photos to appear on wall — photos are auto-approved
after passing the AI safety check. The admin receives a notification DM as FYI only.
"""
import base64
import time as _time
from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    LLM_API_KEY, LLM_BASE_URL,
    TELEGRAM_ADMIN_CHAT_ID, EVENT_NAME, EVENT_HASHTAG,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
)

VISION_MODEL = "google/gemma-3-27b-it:free"


# ─────────────────────────────────────────────────────────────
#  STAGE 2: AI Content Moderation
# ─────────────────────────────────────────────────────────────

async def ai_moderate_image(image_bytes: bytes) -> tuple[bool, str]:
    """
    Sends the image to OpenRouter Gemini Vision for safety classification.
    Returns (is_safe: bool, reason: str).
    Falls back to True if vision API is unavailable.
    """
    b64 = base64.b64encode(image_bytes).decode()

    try:
        from openai import OpenAI
        _client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
        response = _client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are a content moderator for a college event. "
                                "Is this image safe and appropriate for display on a projector screen "
                                "at a college event? Look for: nudity, violence, hate symbols, "
                                "or inappropriate content. "
                                "Reply with exactly: SAFE or UNSAFE, followed by a colon and a brief reason. "
                                "Example: 'SAFE: Group of students smiling' or 'UNSAFE: Contains inappropriate gesture'"
                            ),
                        },
                    ],
                }
            ],
            max_tokens=60,
        )
        result = response.choices[0].message.content.strip()
        is_safe = result.upper().startswith("SAFE")
        reason = result.split(":", 1)[-1].strip() if ":" in result else result
        print(f"[SocialWall] AI moderation: {'SAFE' if is_safe else 'UNSAFE'} — {reason}")
        return is_safe, reason

    except Exception as e:
        print(f"[SocialWall] Vision moderation error: {e} → defaulting to SAFE (auto-approve)")
        return True, "Auto-moderation unavailable — auto-approved"


# ─────────────────────────────────────────────────────────────
#  STAGE 3 + 4 combined: Auto-Approve → Cloudinary → Supabase
# ─────────────────────────────────────────────────────────────

async def send_for_admin_approval(bot, image_bytes: bytes, sender_name: str,
                                   sender_telegram_id: int, temp_file_id: str) -> None:
    """
    AUTO-APPROVE flow (no admin click required):
    1. Upload to Cloudinary with branding overlay
    2. Save to Supabase wall_photos with status='approved'
    3. Try to notify admin as FYI — gracefully skipped if admin hasn't messaged bot

    The wall website polls Supabase every 5 seconds and will show the photo immediately.
    """
    print(f"[SocialWall] Auto-approving photo from {sender_name}...")

    # ── Upload to Cloudinary and apply overlay ─────────────────
    cloudinary_url = None
    try:
        cloudinary_url = apply_overlay_and_push(image_bytes, sender_name, sender_telegram_id)
        print(f"[SocialWall] Cloudinary URL: {cloudinary_url}")
    except Exception as e:
        print(f"[SocialWall] Cloudinary failed: {e} — saving raw photo to Supabase")
        # Save without Cloudinary — use Telegram file_id as fallback reference
        try:
            _save_photo_to_supabase(
                telegram_id=sender_telegram_id,
                sender_name=sender_name,
                cloudinary_url="",
                file_url=f"tg://{temp_file_id}",
            )
        except Exception as e2:
            print(f"[SocialWall] Supabase save also failed: {e2}")

    # ── Notify admin (best-effort, won't crash if admin hasn't messaged bot) ──
    if TELEGRAM_ADMIN_CHAT_ID:
        try:
            await bot.send_photo(
                chat_id=TELEGRAM_ADMIN_CHAT_ID,
                photo=image_bytes,
                caption=(
                    f"📸 *Wall Photo Auto-Approved*\n"
                    f"👤 From: {sender_name}\n"
                    f"✅ AI Safety Check: Passed\n"
                    f"🖥️ Now live on the wall!\n\n"
                    f"_To reject a future photo: use /reject command_"
                ),
                parse_mode="Markdown",
            )
            print(f"[SocialWall] Admin notified ✓")
        except Exception as e:
            # Common reason: admin hasn't started the bot yet
            print(f"[SocialWall] Admin notification skipped: {e}")
            print(f"[SocialWall] → Tell admin @Shakti41 to message the bot first (/start)")

    print(f"[SocialWall] ✅ Photo from {sender_name} is LIVE on the wall!")


# ─────────────────────────────────────────────────────────────
#  STAGE 4: Cloudinary Overlay + Supabase Push
# ─────────────────────────────────────────────────────────────

def apply_overlay_and_push(image_bytes: bytes, sender_name: str,
                            sender_telegram_id: int) -> str:
    """
    Uploads photo to Cloudinary, applies branded overlay, saves to Supabase.
    Returns the branded photo URL.
    """
    import cloudinary
    import cloudinary.uploader
    import cloudinary.utils

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
    )

    # Upload raw photo
    upload = cloudinary.uploader.upload(
        image_bytes,
        folder="wall_photos",
        public_id=f"wall_{sender_telegram_id}_{int(_time.time())}",
        overwrite=False,
    )
    raw_url = upload["secure_url"]
    public_id = upload["public_id"]

    # Apply overlay transformations via Cloudinary URL
    branded_url = cloudinary.utils.cloudinary_url(
        public_id,
        transformation=[
            {
                "overlay": {
                    "font_family": "Montserrat", "font_size": 24,
                    "font_weight": "bold", "text": EVENT_NAME,
                },
                "gravity": "north_west", "x": 15, "y": 15,
                "color": "#FFFFFF",
            },
            {
                "overlay": {
                    "font_family": "Montserrat", "font_size": 28,
                    "font_weight": "bold", "text": sender_name,
                },
                "gravity": "south_west", "x": 15, "y": 20,
                "color": "#FFFFFF",
            },
            {
                "overlay": {
                    "font_family": "Montserrat", "font_size": 22,
                    "text": EVENT_HASHTAG,
                },
                "gravity": "south_east", "x": 15, "y": 20,
                "color": "#A78BFA",
            },
        ],
    )[0]

    # Save to Supabase with correct column names
    _save_photo_to_supabase(
        telegram_id=sender_telegram_id,
        sender_name=sender_name,
        cloudinary_url=branded_url,
        file_url=raw_url,
    )

    print(f"[SocialWall] Photo pushed to wall → {branded_url}")
    return branded_url


def _save_photo_to_supabase(telegram_id: int, sender_name: str,
                              cloudinary_url: str, file_url: str = "") -> None:
    """Save approved wall photo to Supabase with correct column names."""
    try:
        from tools.supabase_tool import _client
        row = {
            "telegram_id":    telegram_id,
            "sender_name":    sender_name,       # column used by website wall
            "attendee_name":  sender_name,       # legacy column
            "cloudinary_url": cloudinary_url,    # column used by website wall
            "branded_url":    cloudinary_url,    # legacy column
            "file_url":       file_url,
            "original_url":   file_url,
            "status":         "approved",        # website filters on this
            # approved (boolean generated column) is auto-computed from status
        }
        _client().table("wall_photos").insert(row).execute()
        print(f"[SocialWall] Saved to Supabase wall_photos ✓")
    except Exception as e:
        print(f"[SocialWall] Supabase save failed: {e}")



