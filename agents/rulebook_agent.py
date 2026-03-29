"""
agents/rulebook_agent.py
Generates a comprehensive event rulebook (markdown → PDF).
"""
from openai import OpenAI
from config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    EVENT_NAME, EVENT_DATE, EVENT_VENUE, OUTPUTS_DIR
)
from tools.pdf_tool import render_rulebook


_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

RULEBOOK_SYSTEM_PROMPT = """You are a professional event coordinator drafting an official rulebook.
Write a comprehensive, well-structured rulebook in markdown format.
Include all sections requested. Use clear headings (# and ##), bullet points, 
and numbered lists. Be specific, formal, and thorough."""


def generate_rulebook(event_plan: dict) -> str:
    """
    Takes the structured event plan from architect_agent and generates
    a full markdown rulebook covering eligibility, rules, judging, and T&C.
    """
    print("[Rulebook] Generating rulebook content...")

    schedule_text = "\n".join(
        f"- {s['time']}: {s['activity']} at {s['location']}"
        for s in event_plan.get("schedule", [])
    )
    activities_text = "\n".join(
        f"- {a['name']}: {a['description']} (Max participants: {a['max_participants']}, Prizes: {a['prizes']})"
        for a in event_plan.get("activities", [])
    )
    rules_text = "\n".join(f"- {r}" for r in event_plan.get("rules", []))
    judging_text = "\n".join(f"- {j}" for j in event_plan.get("judging_criteria", []))

    prompt = f"""
Create a comprehensive official rulebook for the following event:

**Event**: {event_plan.get('event_name')}
**Type**: {event_plan.get('event_type')}
**Date**: {event_plan.get('date')}
**Venue**: {event_plan.get('venue')}
**Theme**: {event_plan.get('theme')}
**Description**: {event_plan.get('description')}

**Schedule**:
{schedule_text}

**Activities**:
{activities_text}

**Key Rules**:
{rules_text}

**Judging Criteria**:
{judging_text}

The rulebook MUST include these sections:
# {event_plan.get('event_name')} — Official Rulebook
## 1. Overview
## 2. Eligibility Criteria
## 3. Registration Process
## 4. Event Schedule (minute-by-minute)
## 5. Activity Rules (one subsection per activity)
## 6. Code of Conduct
## 7. Judging Criteria & Scoring
## 8. Prizes & Recognition
## 9. Disqualification Conditions
## 10. Terms & Conditions
## 11. Contact & Support
"""

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": RULEBOOK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )

    markdown_text = response.choices[0].message.content.strip()

    # Save markdown
    md_path = OUTPUTS_DIR / "rulebooks" / "rulebook.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown_text, encoding="utf-8")
    print(f"[Rulebook] Markdown saved → {md_path}")

    # Render to PDF
    pdf_path = OUTPUTS_DIR / "rulebooks" / "rulebook.pdf"
    render_rulebook(markdown_text, pdf_path, event_plan.get("event_name", EVENT_NAME))

    return markdown_text


if __name__ == "__main__":
    import json
    schedule_path = OUTPUTS_DIR / "schedule.json"
    if schedule_path.exists():
        plan = json.loads(schedule_path.read_text())
        generate_rulebook(plan)
    else:
        print("Run architect_agent.py first to generate schedule.json")
