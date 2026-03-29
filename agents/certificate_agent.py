"""
agents/certificate_agent.py
Generates personalized, Pillow-stamped certificates with a validation QR code.
Triggered when attendee.checked_in = TRUE.
"""
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from config import OUTPUTS_DIR, ASSETS_DIR, EVENT_NAME, EVENT_WEBSITE_URL
from tools.qr_tool import generate_cert_validation_qr
from tools.pdf_tool import image_to_pdf
from tools.supabase_tool import get_all_attendees, save_certificate


# ── Font settings (falls back to default if custom font not available) ───────
def _load_font(size: int, bold: bool = False):
    """Load a font, gracefully falling back to PIL default."""
    font_candidates = [
        ASSETS_DIR / ("Montserrat-Bold.ttf" if bold else "Montserrat-Regular.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in font_candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _draw_centered_text(draw, text: str, y: int, font, fill: str, img_width: int):
    """Draw text centered horizontally on the certificate."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (img_width - text_width) // 2
    draw.text((x, y), text, font=font, fill=fill)


def generate_certificate(
    attendee_id: str,
    name: str,
    rank: str = "Participant",
    template_path: Path | None = None,
) -> Path:
    """
    Stamps a certificate template with the attendee's name + rank + validation QR.
    
    Args:
        attendee_id: UUID from Supabase attendees table
        name: Full name to stamp on certificate
        rank: e.g. '1st Place', 'Participant', 'Finalist'
        template_path: Custom template PNG. Falls back to generated template.
    
    Returns:
        Path to the generated PDF certificate.
    """
    cert_id = str(uuid.uuid4())

    # ── Load or create template ───────────────────────────────────────────────
    if template_path and template_path.exists():
        img = Image.open(template_path).convert("RGBA")
    else:
        # Auto-generate a clean dark certificate if no template provided
        img = _create_default_template()

    img_width, img_height = img.size
    draw = ImageDraw.Draw(img)

    # ── Fonts ────────────────────────────────────────────────────────────────
    font_event   = _load_font(36, bold=True)
    font_name    = _load_font(64, bold=True)
    font_rank    = _load_font(40, bold=False)
    font_tagline = _load_font(24, bold=False)

    # ── Text stamping at calculated coordinates ───────────────────────────────
    # "This certifies that" tagline
    _draw_centered_text(draw, "This certifies that", img_height // 2 - 120, font_tagline, "#CCCCCC", img_width)

    # Participant name (most prominent)
    _draw_centered_text(draw, name.upper(), img_height // 2 - 60, font_name, "#FFFFFF", img_width)

    # "has successfully participated in" tagline
    _draw_centered_text(draw, "has successfully participated in", img_height // 2 + 30, font_tagline, "#CCCCCC", img_width)

    # Event name
    _draw_centered_text(draw, EVENT_NAME.upper(), img_height // 2 + 70, font_event, "#A78BFA", img_width)

    # Rank
    _draw_centered_text(draw, f"🏆 {rank}", img_height // 2 + 130, font_rank, "#FFD700", img_width)

    # ── Validation QR code (bottom-right corner) ──────────────────────────────
    qr_img = generate_cert_validation_qr(cert_id, size=120)
    qr_x = img_width - 150
    qr_y = img_height - 150
    img.paste(qr_img, (qr_x, qr_y))

    # Small "Verify at:" label above QR
    draw.text((qr_x, qr_y - 20), "Scan to verify", font=_load_font(16), fill="#AAAAAA")

    # ── Save stamped image ────────────────────────────────────────────────────
    img_path = OUTPUTS_DIR / "certificates" / f"cert_{attendee_id}.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(str(img_path), quality=95)

    # ── Wrap into PDF ─────────────────────────────────────────────────────────
    pdf_path = OUTPUTS_DIR / "certificates" / f"cert_{attendee_id}.pdf"
    image_to_pdf(img_path, pdf_path)

    # ── Save to Supabase ──────────────────────────────────────────────────────
    try:
        save_certificate(attendee_id, str(pdf_path), rank)
    except Exception as e:
        print(f"[Certificate] Supabase save failed (offline mode?): {e}")

    print(f"[Certificate] Generated for {name} ({rank}) → {pdf_path}")
    return pdf_path


def _create_default_template() -> Image.Image:
    """Creates a professional dark certificate template with Pillow if no custom template exists."""
    W, H = 1684, 1191  # A4 landscape @ 200dpi
    img = Image.new("RGBA", (W, H), "#0D0D1A")
    draw = ImageDraw.Draw(img)

    # Gradient-like border using rectangles
    for i, color in [(0, "#6D28D9"), (8, "#A78BFA"), (16, "#6D28D9")]:
        draw.rectangle([i, i, W - i, H - i], outline=color, width=3)

    # Decorative corner accents
    accent = "#A78BFA"
    sz = 60
    for (x, y) in [(0, 0), (W - sz, 0), (0, H - sz), (W - sz, H - sz)]:
        draw.rectangle([x, y, x + sz, y + sz], fill=accent)
        draw.rectangle([x + 8, y + 8, x + sz - 8, y + sz - 8], fill="#0D0D1A")

    # Event name header
    font_header = _load_font(28, bold=True)
    draw.text((60, 60), EVENT_NAME.upper(), font=font_header, fill="#A78BFA")

    # Horizontal divider lines
    draw.line([(60, 110), (W - 60, 110)], fill="#6D28D9", width=2)
    draw.line([(60, H - 110), (W - 60, H - 110)], fill="#6D28D9", width=2)

    return img


def run_all_certificates(rank_mapping: dict | None = None) -> list[Path]:
    """
    Generates certificates for all checked-in attendees.
    rank_mapping: {attendee_id: rank_string} — optional, defaults to 'Participant'
    """
    from tools.supabase_tool import get_checked_in_attendees
    attendees = get_checked_in_attendees()
    paths = []
    for a in attendees:
        rank = (rank_mapping or {}).get(a["id"], "Participant")
        path = generate_certificate(
            attendee_id=a["id"],
            name=a["name"],
            rank=rank,
        )
        paths.append(path)
    print(f"[Certificate] Generated {len(paths)} certificates.")
    return paths


async def send_certificates_via_telegram(
    bot,
    rank_mapping: dict | None = None,
    progress_callback=None,
) -> dict:
    """
    Generate certificates for all checked-in attendees AND send them via Telegram DM.

    Args:
        bot: Telegram bot instance
        rank_mapping: {attendee_id: rank_string} — optional
        progress_callback: Optional async callable(sent, total) for real-time progress

    Returns:
        {"sent": N, "failed": N, "no_telegram": N, "total": N}
    """
    from tools.supabase_tool import get_checked_in_attendees
    import io

    attendees = get_checked_in_attendees()
    result = {"sent": 0, "failed": 0, "no_telegram": 0, "total": len(attendees)}

    for i, a in enumerate(attendees):
        rank = (rank_mapping or {}).get(a["id"], "Participant")

        # Generate certificate
        try:
            pdf_path = generate_certificate(
                attendee_id=a["id"],
                name=a["name"],
                rank=rank,
            )
        except Exception as e:
            print(f"[Certificate] Generation failed for {a['name']}: {e}")
            result["failed"] += 1
            continue

        # Send via Telegram if telegram_id exists
        if not a.get("telegram_id"):
            result["no_telegram"] += 1
            continue

        try:
            caption = (
                f"🎓 *Your Certificate is Here!*\n\n"
                f"Congratulations, *{a['name']}*!\n"
                f"You have successfully participated in *{EVENT_NAME}* as *{rank}*.\n\n"
                f"🔍 Scan the QR code on your certificate to verify it online.\n"
                f"Thank you for being a part of this event! 🙌\n\n"
                f"— 🤖 PFL Event Management"
            )
            with open(pdf_path, "rb") as f:
                await bot.send_document(
                    chat_id=a["telegram_id"],
                    document=f,
                    filename=f"Certificate_{a['name'].replace(' ', '_')}.pdf",
                    caption=caption,
                    parse_mode="Markdown",
                )
            result["sent"] += 1
            print(f"[Certificate] ✅ Sent to {a['name']} ({a['telegram_id']})")
        except Exception as e:
            print(f"[Certificate] ❌ Failed to send to {a['name']}: {e}")
            result["failed"] += 1

        if progress_callback:
            await progress_callback(i + 1, len(attendees))

    print(f"[Certificate] Delivery complete: {result}")
    return result


async def collect_feedback(bot, event_name: str = EVENT_NAME) -> bool:
    """
    Send a post-event feedback poll to all attendees via Telegram DM and group.

    Returns True if at least one message was sent.
    """
    from tools.supabase_tool import get_checked_in_attendees

    poll_question = f"⭐ How would you rate {event_name}?"
    poll_options = ["⭐ 1 - Poor", "⭐⭐ 2 - Below Average", "⭐⭐⭐ 3 - Average",
                    "⭐⭐⭐⭐ 4 - Good", "⭐⭐⭐⭐⭐ 5 - Excellent!"]

    follow_up = (
        f"🙏 Thank you for attending *{event_name}*!\n\n"
        f"We'd love your feedback to make our future events even better.\n"
        f"Please take 30 seconds to fill out our quick survey:"
        f"\n\nPlease reply to this message with your suggestions! 💬"
    )

    attendees = get_checked_in_attendees()
    sent = 0

    for a in attendees:
        if not a.get("telegram_id"):
            continue
        try:
            await bot.send_poll(
                chat_id=a["telegram_id"],
                question=poll_question,
                options=poll_options,
                is_anonymous=False,
            )
            await bot.send_message(
                chat_id=a["telegram_id"],
                text=follow_up,
                parse_mode="Markdown",
            )
            sent += 1
        except Exception as e:
            print(f"[Certificate] Failed to send feedback to {a.get('name')}: {e}")

    print(f"[Certificate] Feedback polls sent to {sent} attendees")
    return sent > 0


if __name__ == "__main__":
    # Test with a dummy attendee
    test_path = generate_certificate(
        attendee_id="test-123",
        name="Shakti Patel",
        rank="1st Place",
    )
    print(f"Test certificate: {test_path}")

