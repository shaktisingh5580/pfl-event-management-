"""
agents/comms_agent.py
Communication Hub — personalized DMs, group blasts, welcome PDFs,
auto Telegram group invite links, and trigger-based messages.
"""
import io
from pathlib import Path
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from jinja2 import Template
from config import (
    EVENT_NAME, EVENT_DATE, EVENT_VENUE, EVENT_HASHTAG,
    TELEGRAM_GROUP_CHAT_ID, OUTPUTS_DIR
)
from tools.qr_tool import generate_ticket_qr
from tools.supabase_tool import get_all_attendees, get_attendee_by_telegram


# ─────────────────────────────────────────────────────────────
#  WELCOME PDF (sent on registration)
# ─────────────────────────────────────────────────────────────

def generate_welcome_pdf(attendee: dict, schedule: list[dict]) -> Path:
    """
    Generates a personalized Welcome PDF for a new registrant containing:
    - Their name + unique QR ticket
    - Seat assignment and coordinator contact
    - Full event schedule
    """
    attendee_id = attendee["id"]
    out_path = OUTPUTS_DIR / "tickets" / f"welcome_{attendee_id}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, spaceAfter=8)
    body_style  = ParagraphStyle("Body",  parent=styles["Normal"], fontSize=11, leading=16)
    info_style  = ParagraphStyle("Info",  parent=styles["Normal"], fontSize=12, spaceAfter=4, textColor=colors.HexColor("#6D28D9"))

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # Header
    story.append(Paragraph(f"🎉 Welcome to {EVENT_NAME}!", title_style))
    story.append(Paragraph(f"Hello <b>{attendee['name']}</b>, you're officially registered!", body_style))
    story.append(Spacer(1, 0.5*cm))

    # Event Info
    story.append(Paragraph(f"📅 <b>Date:</b> {EVENT_DATE}", info_style))
    story.append(Paragraph(f"📍 <b>Venue:</b> {EVENT_VENUE}", info_style))
    story.append(Paragraph(f"💺 <b>Your Seat:</b> {attendee.get('seat', 'TBA')}", info_style))
    story.append(Paragraph(f"👤 <b>Your Coordinator:</b> {attendee.get('coordinator', 'TBA')}", info_style))
    story.append(Spacer(1, 0.5*cm))

    # QR Ticket
    qr_path = generate_ticket_qr(attendee_id, attendee["name"])
    story.append(Paragraph("🎫 <b>Your Entry QR Code</b> (show this at the gate):", body_style))
    story.append(Spacer(1, 0.2*cm))
    story.append(RLImage(str(qr_path), width=4*cm, height=4*cm))
    story.append(Spacer(1, 0.5*cm))

    # Schedule table
    if schedule:
        story.append(Paragraph("📋 <b>Event Schedule</b>", body_style))
        story.append(Spacer(1, 0.2*cm))
        table_data = [["Time", "Activity", "Location"]]
        for slot in schedule:
            table_data.append([slot.get("time", ""), slot.get("activity", ""), slot.get("location", "")])

        tbl = Table(table_data, colWidths=[3*cm, 9*cm, 5*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F3FF")]),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#C4B5FD")),
            ("PADDING",     (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph(f"See you there! {EVENT_HASHTAG}", info_style))
    doc.build(story)
    print(f"[Comms] Welcome PDF → {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────
#  PERSONALIZED DMs
# ─────────────────────────────────────────────────────────────

async def send_personalized_dm(bot, template_message: str, filters: dict | None = None) -> int:
    """
    Sends personalized DMs to attendees by rendering a Jinja2 template.
    
    Args:
        bot: Telegram bot instance
        template_message: Jinja2 template string, e.g.:
            "Hi {{ name }}, your round starts in 10 mins at Table {{ seat }}!"
        filters: Supabase-style filters dict, e.g. {"round": "final"}
                 None = send to all attendees with telegram_id
    
    Returns:
        Number of messages sent successfully.
    """
    attendees = get_all_attendees()
    tmpl = Template(template_message)
    sent = 0

    for attendee in attendees:
        if not attendee.get("telegram_id"):
            continue

        # Apply filters
        if filters:
            skip = False
            for key, val in filters.items():
                if str(attendee.get(key, "")) != str(val):
                    skip = True
                    break
            if skip:
                continue

        msg = tmpl.render(**attendee)
        try:
            await bot.send_message(chat_id=attendee["telegram_id"], text=msg, parse_mode="HTML")
            sent += 1
        except Exception as e:
            print(f"[Comms] DM failed to {attendee['name']}: {e}")

    print(f"[Comms] Sent {sent} personalized DMs.")
    return sent


# ─────────────────────────────────────────────────────────────
#  GROUP BLAST
# ─────────────────────────────────────────────────────────────

async def send_group_blast(bot, message: str, parse_mode: str = "HTML") -> bool:
    """
    Sends an announcement to the entire event Telegram group.
    Supports HTML formatting: <b>bold</b>, <i>italic</i>
    """
    try:
        await bot.send_message(
            chat_id=TELEGRAM_GROUP_CHAT_ID,
            text=message,
            parse_mode=parse_mode,
        )
        print(f"[Comms] Group blast sent to {TELEGRAM_GROUP_CHAT_ID}")
        return True
    except Exception as e:
        print(f"[Comms] Group blast failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
#  AUTO TELEGRAM GROUP INVITE
# ─────────────────────────────────────────────────────────────

async def generate_invite_link(bot) -> str:
    """
    Generates a unique one-time Telegram invite link for the event group.
    The link expires after 1 use (member_limit=1) for security.
    """
    try:
        link = await bot.create_chat_invite_link(
            chat_id=TELEGRAM_GROUP_CHAT_ID,
            member_limit=1,
            name="Registration Auto-Invite",
        )
        return link.invite_link
    except Exception as e:
        print(f"[Comms] Invite link generation failed: {e}")
        return ""
