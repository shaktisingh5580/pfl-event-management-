"""
agents/report_agent.py
Sponsor ROI & Post-Event Report Generator for PFL Event Management.

Generates a beautiful PDF report with:
  - Event overview stats (registrations, check-ins, completion rate)
  - Social wall engagement (photos uploaded, approved)
  - AI Networking stats (matches made, accepted)
  - Complaint resolution summary
  - Feedback sentiment summary
  - Sponsor exposure data (page views, registrations attributed)

Delivered as a PDF using ReportLab.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from config import EVENT_NAME, EVENT_DATE, EVENT_VENUE, OUTPUTS_DIR
from tools.supabase_tool import _client as _sb


# ─── Data Collection ─────────────────────────────────────────────────────────

def _collect_stats() -> dict:
    """Fetch all event metrics from Supabase."""
    sb = _sb()
    stats = {}

    try:
        # Total registrations
        res = sb.table("attendees").select("id, checked_in, source, telegram_id").execute()
        attendees = res.data or []
        stats["total_registered"] = len(attendees)
        stats["total_checked_in"] = sum(1 for a in attendees if a.get("checked_in"))
        stats["telegram_linked"] = sum(1 for a in attendees if a.get("telegram_id"))
        stats["from_website"] = sum(1 for a in attendees if a.get("source") == "website")
        stats["from_telegram"] = sum(1 for a in attendees if a.get("source") == "telegram")
        if stats["total_registered"] > 0:
            stats["checkin_rate"] = round(100 * stats["total_checked_in"] / stats["total_registered"], 1)
        else:
            stats["checkin_rate"] = 0
    except Exception as e:
        print(f"[Report] Attendee stats error: {e}")
        stats.update({"total_registered": 0, "total_checked_in": 0, "checkin_rate": 0,
                      "telegram_linked": 0, "from_website": 0, "from_telegram": 0})

    try:
        # Wall photos
        wall_res = sb.table("wall_photos").select("id, status").execute()
        wall = wall_res.data or []
        stats["wall_total"] = len(wall)
        stats["wall_approved"] = sum(1 for p in wall if p.get("status") == "approved")
    except Exception:
        stats.update({"wall_total": 0, "wall_approved": 0})

    try:
        # Complaints
        comp_res = sb.table("complaints").select("id, severity, status, category").execute()
        complaints = comp_res.data or []
        stats["complaints_total"] = len(complaints)
        stats["complaints_resolved"] = sum(1 for c in complaints if c.get("status") == "resolved")
        stats["complaints_by_severity"] = {
            "emergency": sum(1 for c in complaints if c.get("severity") == "emergency"),
            "high": sum(1 for c in complaints if c.get("severity") == "high"),
            "medium": sum(1 for c in complaints if c.get("severity") == "medium"),
            "low": sum(1 for c in complaints if c.get("severity") == "low"),
        }
        stats["complaints_by_category"] = {}
        for c in complaints:
            cat = c.get("category", "Other")
            stats["complaints_by_category"][cat] = stats["complaints_by_category"].get(cat, 0) + 1
    except Exception:
        stats.update({"complaints_total": 0, "complaints_resolved": 0,
                      "complaints_by_severity": {}, "complaints_by_category": {}})

    try:
        # Matches
        match_res = sb.table("match_interactions").select("status").execute()
        matches = match_res.data or []
        stats["matches_sent"] = len(matches)
        stats["matches_accepted"] = sum(1 for m in matches if m.get("status") == "accepted")
    except Exception:
        stats.update({"matches_sent": 0, "matches_accepted": 0})

    try:
        # Certificates
        cert_res = sb.table("certificates").select("id").execute()
        stats["certificates_issued"] = len(cert_res.data or [])
    except Exception:
        stats["certificates_issued"] = 0

    try:
        # Feedback
        fb_res = sb.table("feedback").select("id, rating, sentiment").execute()
        feedback = fb_res.data or []
        stats["feedback_count"] = len(feedback)
        ratings = [f.get("rating", 0) for f in feedback if f.get("rating")]
        stats["avg_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else 0
        stats["feedback_positive"] = sum(1 for f in feedback if f.get("sentiment") == "positive")
        stats["feedback_negative"] = sum(1 for f in feedback if f.get("sentiment") == "negative")
    except Exception:
        stats.update({"feedback_count": 0, "avg_rating": 0, "feedback_positive": 0, "feedback_negative": 0})

    return stats


# ─── PDF Report Builder ───────────────────────────────────────────────────────

def generate_roi_report(event_plan: dict | None = None) -> Path:
    """
    Generate the post-event ROI and summary PDF report.

    Returns path to the generated PDF.
    """
    print("[Report] Collecting stats from Supabase...")
    stats = _collect_stats()
    plan = event_plan or {}

    out_path = OUTPUTS_DIR / "reports" / f"roi_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PFLTitle", parent=styles["Title"], fontSize=24,
                                  textColor=colors.HexColor("#6D28D9"), alignment=TA_CENTER)
    subtitle_style = ParagraphStyle("PFLSub", parent=styles["Normal"], fontSize=12,
                                     textColor=colors.HexColor("#7C3AED"), alignment=TA_CENTER)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=14,
                                    textColor=colors.HexColor("#1E1B4B"), spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=16)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9,
                                  textColor=colors.HexColor("#6D28D9"))

    story = []

    # ── Header ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("PFL Event Management", subtitle_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Post-Event ROI Report", title_style))
    story.append(Spacer(1, 0.2*cm))
    event_name = plan.get("event_name", EVENT_NAME)
    event_date = plan.get("date", EVENT_DATE)
    event_venue = plan.get("venue", EVENT_VENUE)
    story.append(Paragraph(f"{event_name} | {event_date} | {event_venue}", subtitle_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}", label_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#A78BFA")))
    story.append(Spacer(1, 0.5*cm))

    # ── Highlight Cards (2x3 grid) ─────────────────────────────────────────────
    story.append(Paragraph("📊 Event Highlights", section_style))

    def _stat_cell(label: str, value: str, sub: str = "") -> list:
        return [
            Paragraph(f"<b>{value}</b>", ParagraphStyle("Val", fontSize=22,
                       textColor=colors.HexColor("#6D28D9"), alignment=TA_CENTER)),
            Paragraph(label, ParagraphStyle("Lbl", fontSize=9, textColor=colors.grey, alignment=TA_CENTER)),
            Paragraph(sub, ParagraphStyle("Sub", fontSize=8, textColor=colors.HexColor("#A78BFA"), alignment=TA_CENTER)),
        ]

    highlight_data = [
        [
            _stat_cell("Registrations", str(stats["total_registered"]), "Total sign-ups"),
            _stat_cell("Checked In", str(stats["total_checked_in"]), f"{stats['checkin_rate']}% attendance"),
            _stat_cell("Certificates", str(stats["certificates_issued"]), "Issued"),
        ],
        [
            _stat_cell("Wall Photos", str(stats["wall_approved"]), f"{stats['wall_total']} uploaded"),
            _stat_cell("AI Matches", str(stats["matches_accepted"]), f"{stats['matches_sent']} sent"),
            _stat_cell("Avg Rating", f"{stats['avg_rating']}/5", f"{stats['feedback_count']} responses"),
        ],
    ]

    for row in highlight_data:
        tbl = Table(
            [row],
            colWidths=[5.5*cm, 5.5*cm, 5.5*cm],
            rowHeights=[2.5*cm],
        )
        tbl.setStyle(TableStyle([
            ("BOX",         (0, 0), (-1, -1), 0.5, colors.HexColor("#A78BFA")),
            ("INNERGRID",   (0, 0), (-1, -1), 0.5, colors.HexColor("#EDE9FE")),
            ("BACKGROUND",  (0, 0), (-1, -1), colors.HexColor("#F5F3FF")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("ROWPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3*cm))

    # ── Registration Breakdown ──────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#EDE9FE")))
    story.append(Paragraph("📝 Registration Breakdown", section_style))
    reg_table = Table([
        ["Source", "Count", "% of Total"],
        ["Website", stats["from_website"], f"{round(100*stats['from_website']/max(stats['total_registered'],1),1)}%"],
        ["Telegram Bot", stats["from_telegram"], f"{round(100*stats['from_telegram']/max(stats['total_registered'],1),1)}%"],
        ["Telegram Linked", stats["telegram_linked"], f"{round(100*stats['telegram_linked']/max(stats['total_registered'],1),1)}%"],
        ["TOTAL", stats["total_registered"], "100%"],
    ], colWidths=[7*cm, 4*cm, 4*cm])
    reg_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1E1B4B")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -3), [colors.white, colors.HexColor("#F5F3FF")]),
        ("BACKGROUND",  (0, -1), (-1, -1), colors.HexColor("#EDE9FE")),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#C4B5FD")),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
        ("PADDING",     (0, 0), (-1, -1), 8),
    ]))
    story.append(reg_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Complaints ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#EDE9FE")))
    story.append(Paragraph("🆘 Complaints & Help Desk", section_style))
    resolved_pct = round(100 * stats["complaints_resolved"] / max(stats["complaints_total"], 1), 1)
    story.append(Paragraph(
        f"Total complaints received: <b>{stats['complaints_total']}</b> | "
        f"Resolved: <b>{stats['complaints_resolved']}</b> ({resolved_pct}%)", body_style
    ))
    story.append(Spacer(1, 0.3*cm))

    sev = stats.get("complaints_by_severity", {})
    if any(sev.values()):
        sev_data = [["Severity", "Count"]] + [[k.title(), v] for k, v in sev.items() if v > 0]
        sev_table = Table(sev_data, colWidths=[6*cm, 4*cm])
        sev_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#991B1B")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#FCA5A5")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FEF2F2")]),
            ("PADDING",     (0, 0), (-1, -1), 6),
            ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ]))
        story.append(sev_table)
    story.append(Spacer(1, 0.5*cm))

    # ── AI Networking ─────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#EDE9FE")))
    story.append(Paragraph("🤝 AI Networking Performance", section_style))
    accept_rate = round(100 * stats["matches_accepted"] / max(stats["matches_sent"], 1), 1)
    story.append(Paragraph(
        f"AI-generated networking suggestions: <b>{stats['matches_sent']}</b> | "
        f"Accepted by attendees: <b>{stats['matches_accepted']}</b> ({accept_rate}% acceptance rate)",
        body_style
    ))
    story.append(Spacer(1, 0.5*cm))

    # ── Feedback Summary ──────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#EDE9FE")))
    story.append(Paragraph("💬 Feedback Summary", section_style))
    story.append(Paragraph(
        f"Total feedback responses: <b>{stats['feedback_count']}</b> | "
        f"Average rating: <b>{stats['avg_rating']}/5 ⭐</b> | "
        f"Positive: <b>{stats['feedback_positive']}</b> | "
        f"Negative: <b>{stats['feedback_negative']}</b>",
        body_style
    ))
    story.append(Spacer(1, 0.5*cm))

    # ── For Sponsors ─────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#EDE9FE")))
    story.append(Paragraph("📣 Sponsor Visibility Report", section_style))
    story.append(Paragraph(
        f"This event reached <b>{stats['total_registered']}</b> registered participants "
        f"with <b>{stats['total_checked_in']}</b> physical attendees. "
        f"Sponsor branding was visible on the event website, printed posters (with QR codes), "
        f"Telegram group broadcasts ({stats.get('telegram_linked', 0)} members), "
        f"and all <b>{stats['certificates_issued']}</b> digital certificates issued to participants.",
        body_style
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Social Wall: <b>{stats['wall_approved']}</b> event photos shared publicly with event branding overlays.",
        body_style
    ))
    story.append(Spacer(1, 1*cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#A78BFA")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Generated by <b>PFL Event Management AI System</b> · powered by AI agents",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.gray, alignment=TA_CENTER)
    ))

    doc.build(story)
    print(f"[Report] ✅ ROI Report saved → {out_path}")
    return out_path
