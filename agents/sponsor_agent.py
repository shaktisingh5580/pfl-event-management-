"""
agents/sponsor_agent.py
Sponsor Discovery & Email Outreach Agent for PFL Event Management.

Features:
  1. Filter sponsors by event type
  2. LLM-drafted personalized sponsorship email
  3. One-click SMTP email blast
  4. Manual call list export
"""
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, BASE_DIR, EVENT_NAME, EVENT_DATE, EVENT_VENUE

_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

SPONSORS_DB_PATH = BASE_DIR / "data" / "sponsors.json"


# ─── Sponsor Database ─────────────────────────────────────────────────────────

def load_sponsors() -> dict:
    """Load the full sponsor database."""
    if SPONSORS_DB_PATH.exists():
        return json.loads(SPONSORS_DB_PATH.read_text(encoding="utf-8"))
    return {"sponsors": [], "tiers": {}}


def get_sponsors_for_event(event_type_id: str, limit: int = 20) -> list[dict]:
    """
    Filter sponsors relevant to the given event type.

    Args:
        event_type_id: Template ID e.g. 'techfest', 'hackathon', 'sports_event'
        limit: Max sponsors to return
    """
    db = load_sponsors()
    relevant = [
        s for s in db["sponsors"]
        if event_type_id in s.get("relevant_for", [])
    ]
    # Sort: Platinum → Gold → Silver → Bronze
    tier_order = {"Platinum": 0, "Gold": 1, "Silver": 2, "Bronze": 3}
    relevant.sort(key=lambda s: tier_order.get(s.get("tier_typically", "Bronze"), 4))
    return relevant[:limit]


def get_all_tiers() -> dict:
    """Return tier definitions (contribution amounts and benefits)."""
    return load_sponsors().get("tiers", {})


# ─── Email Draft Generation ───────────────────────────────────────────────────

def draft_sponsorship_email(
    sponsor: dict,
    event_plan: dict,
    organizer_name: str = "The Organizing Team",
    organizer_email: str = "",
    organizer_phone: str = "",
) -> str:
    """
    Generate a personalized sponsorship proposal email using LLM.

    Returns the full email body as a string.
    """
    tiers = get_all_tiers()
    tier_name = sponsor.get("tier_typically", "Gold")
    tier_info = tiers.get(tier_name, {})
    benefits_list = "\n".join(f"  • {b}" for b in tier_info.get("benefits", []))
    min_contribution = tier_info.get("min_contribution_inr", 20000)

    prompt = f"""You are writing a professional sponsorship proposal email on behalf of {organizer_name} for PFL Event Management.

Event Details:
- Event Name: {event_plan.get('event_name', EVENT_NAME)}
- Event Type: {event_plan.get('event_type', 'Technical Festival')}
- Date: {event_plan.get('date', EVENT_DATE)}
- Venue: {event_plan.get('venue', EVENT_VENUE)}
- Expected Participants: {event_plan.get('total_participants_expected', 200)}+
- Theme: {event_plan.get('theme', 'Technology & Innovation')}

Sponsor Company: {sponsor['company']}
Industry: {sponsor['industry']}
Proposed Tier: {tier_name} Sponsor

What this company typically offers: {sponsor.get('notes', '')}

Sponsorship Benefits we are offering ({tier_name} Tier — Min ₹{min_contribution:,}):
{benefits_list}

Write a professional, warm, and compelling sponsorship proposal email. 
- Subject line first (prefix with "Subject: ")
- Keep it under 300 words
- Be specific about mutual benefits
- Mention the student audience (college event)
- End with a clear call to action to reply or call
- Sign off as: {organizer_name}, PFL Event Management
  Email: {organizer_email or '[organizer_email]'}
  Phone: {organizer_phone or '[organizer_phone]'}

Write ONLY the email (subject + body), no extra commentary."""

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


# ─── Email Sending ────────────────────────────────────────────────────────────

def send_sponsor_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    smtp_password: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> bool:
    """
    Send a single sponsorship email via SMTP.

    For Gmail: enable 2FA + use an App Password.
    Returns True on success, False on failure.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        # Plain text version
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(from_email, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

        print(f"[Sponsor] ✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Sponsor] ❌ Failed to send to {to_email}: {e}")
        return False


def blast_sponsor_emails(
    sponsor_ids_or_all: list[str] | None,
    event_plan: dict,
    event_type_id: str,
    organizer_name: str,
    from_email: str,
    smtp_password: str,
    organizer_phone: str = "",
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> dict:
    """
    Send personalized sponsorship emails to a list of sponsors.

    Args:
        sponsor_ids_or_all: List of company names, or None to send to all relevant
        event_plan: Event plan dict from architect
        event_type_id: Template ID for filtering
        organizer_name: Name of the organizing team/person
        from_email: Sender's Gmail address
        smtp_password: Gmail App Password
        organizer_phone: Optional phone to include in email
        smtp_host: SMTP host (default Gmail)
        smtp_port: SMTP port (default 587)

    Returns:
        {"sent": [...], "failed": [...], "skipped": [...]}
    """
    all_sponsors = get_sponsors_for_event(event_type_id)

    if sponsor_ids_or_all:
        sponsors = [s for s in all_sponsors if s["company"] in sponsor_ids_or_all]
    else:
        sponsors = all_sponsors

    results = {"sent": [], "failed": [], "skipped": []}

    for sponsor in sponsors:
        if not sponsor.get("contact_email"):
            print(f"[Sponsor] ⚠️  No email for {sponsor['company']} — skipping")
            results["skipped"].append(sponsor["company"])
            continue

        print(f"[Sponsor] Drafting email for {sponsor['company']}...")
        full_draft = draft_sponsorship_email(
            sponsor=sponsor,
            event_plan=event_plan,
            organizer_name=organizer_name,
            organizer_email=from_email,
            organizer_phone=organizer_phone,
        )

        # Parse subject from draft
        lines = full_draft.split("\n")
        subject = ""
        body_lines = []
        for i, line in enumerate(lines):
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
            else:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()

        if not subject:
            subject = f"Sponsorship Proposal — {event_plan.get('event_name', EVENT_NAME)}"

        success = send_sponsor_email(
            to_email=sponsor["contact_email"],
            subject=subject,
            body=body,
            from_email=from_email,
            smtp_password=smtp_password,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
        )
        if success:
            results["sent"].append(sponsor["company"])
        else:
            results["failed"].append(sponsor["company"])

    print(f"\n[Sponsor] Blast complete: {len(results['sent'])} sent, "
          f"{len(results['failed'])} failed, {len(results['skipped'])} skipped")
    return results


# ─── Call List Export ─────────────────────────────────────────────────────────

def get_call_list(event_type_id: str) -> list[dict]:
    """
    Returns sponsors with phone numbers for manual outreach.
    """
    sponsors = get_sponsors_for_event(event_type_id)
    return [
        {
            "company": s["company"],
            "industry": s["industry"],
            "phone": s.get("phone", "N/A"),
            "tier": s.get("tier_typically", "Silver"),
            "notes": s.get("notes", ""),
        }
        for s in sponsors if s.get("phone")
    ]


# ─── Preview Email (for dashboard) ───────────────────────────────────────────

def preview_sponsor_email(
    sponsor_company: str,
    event_type_id: str,
    event_plan: dict,
    organizer_name: str = "The Organizing Team",
    organizer_email: str = "",
    organizer_phone: str = "",
) -> dict:
    """
    Generate a preview of the sponsorship email for a specific company.
    Returns {"subject": str, "body": str, "sponsor": dict}
    """
    all_sponsors = get_sponsors_for_event(event_type_id)
    sponsor = next((s for s in all_sponsors if s["company"] == sponsor_company), None)

    if not sponsor:
        # Try full DB
        db = load_sponsors()
        sponsor = next((s for s in db["sponsors"] if s["company"] == sponsor_company), None)

    if not sponsor:
        return {"error": f"Sponsor '{sponsor_company}' not found"}

    full_draft = draft_sponsorship_email(
        sponsor=sponsor,
        event_plan=event_plan,
        organizer_name=organizer_name,
        organizer_email=organizer_email,
        organizer_phone=organizer_phone,
    )

    lines = full_draft.split("\n")
    subject = ""
    body_lines = []
    for line in lines:
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
        else:
            body_lines.append(line)

    return {
        "subject": subject or f"Sponsorship Proposal — {event_plan.get('event_name', EVENT_NAME)}",
        "body": "\n".join(body_lines).strip(),
        "sponsor": sponsor,
    }
