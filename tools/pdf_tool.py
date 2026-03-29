"""
tools/pdf_tool.py
PDF generation utilities: rulebook formatter and certificate PDF wrapper.
Uses ReportLab for layout and Pillow for image stamping.
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from pathlib import Path
import io


# ──────────────────────────────────────────────────
#  RULEBOOK PDF
# ──────────────────────────────────────────────────

def render_rulebook(markdown_text: str, output_path: Path, event_name: str) -> Path:
    """
    Convert the AI-generated rulebook markdown into a formatted PDF.
    Handles headings (# ##), bullet points, and paragraphs.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle(
        "EventTitle",
        parent=styles["Title"],
        fontSize=22, spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER,
    )
    h1_style = ParagraphStyle(
        "H1", parent=styles["Heading1"],
        fontSize=16, spaceBefore=14, spaceAfter=4,
        textColor=colors.HexColor("#16213e"),
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=13, spaceBefore=10, spaceAfter=2,
        textColor=colors.HexColor("#0f3460"),
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=15, spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        "Bullet", parent=body_style,
        leftIndent=20, bulletIndent=10,
    )

    # Title
    story.append(Paragraph(event_name, title_style))
    story.append(Paragraph("Official Rulebook", styles["Italic"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e94560")))
    story.append(Spacer(1, 0.4*cm))

    # Parse markdown line by line
    for line in markdown_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.2*cm))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], h1_style))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], h2_style))
        elif line.startswith("- ") or line.startswith("* "):
            story.append(Paragraph(f"• {line[2:]}", bullet_style))
        else:
            story.append(Paragraph(line, body_style))

    doc.build(story)
    print(f"[PDF] Rulebook saved → {output_path}")
    return output_path


# ──────────────────────────────────────────────────
#  CERTIFICATE PDF WRAPPER
# ──────────────────────────────────────────────────

def image_to_pdf(image_path: Path, output_path: Path) -> Path:
    """
    Wraps a Pillow-stamped certificate image (PNG) into a portrait PDF.
    The certificate_agent.py does all the Pillow stamping first,
    then calls this to produce the final deliverable PDF.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        rightMargin=0, leftMargin=0,
        topMargin=0, bottomMargin=0,
    )
    # A4 landscape: 842 x 595 pts
    img = RLImage(str(image_path), width=842, height=595)
    doc.build([img])
    print(f"[PDF] Certificate PDF saved → {output_path}")
    return output_path
