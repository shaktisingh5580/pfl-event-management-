"""
agents/architect_agent.py
AI Architect — generates event schedule, activity list, and resource plan.
Triggered at the very start of the pre-event flow.

Supports:
  - Template-based quick start (5 event types with pre-filled context)
  - API-friendly stateless chat (history passed in, reply returned)
  - Legacy interactive CLI mode
"""
import json
from pathlib import Path
from openai import OpenAI
from config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    EVENT_NAME, EVENT_DATE, EVENT_VENUE, OUTPUTS_DIR, BASE_DIR
)

_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

# ─── Template Loader ─────────────────────────────────────────────────────────

TEMPLATES_PATH = BASE_DIR / "templates" / "event_templates.json"

def load_templates() -> list[dict]:
    """Load all available event templates from templates/event_templates.json."""
    if TEMPLATES_PATH.exists():
        return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8")).get("templates", [])
    return []


def get_template_by_id(template_id: str) -> dict | None:
    """Fetch a single template by its ID."""
    for t in load_templates():
        if t["id"] == template_id:
            return t
    return None


def get_templates_summary() -> str:
    """Human-readable list of available templates for display."""
    templates = load_templates()
    lines = ["📋 *Available Event Templates:*\n"]
    for t in templates:
        lines.append(f"  {t['icon']} **{t['name']}** (`{t['id']}`)")
        lines.append(f"     _{t['description']}_\n")
    return "\n".join(lines)


# ─── System Prompt ────────────────────────────────────────────────────────────

def _build_system_prompt(template: dict | None = None) -> str:
    base = """You are an expert event architect for PFL Event Management, helping plan an event.
Your mission: gather ALL required information through a natural conversation.

You must ask questions to collect:
1. Event Name, Type, Date, Venue, Theme
2. Total Participants Expected
3. Schedule of Activities (what, when, where, which room/hall)
4. Resources (rooms with capacity, equipment, volunteers, budget)
5. Rules & Judging Criteria
6. Coordinators names for each activity
7. **Custom Registration Fields**: exactly what info to collect from attendees at registration.
   Ask the organizer what specific information they need from participants BEYOND the standard fields
   (name, email, phone, college, skills, interests are always collected).
   
   Event-type-specific examples to guide your questions:
   - Cricket/Sports: team name, captain name, player names (with count), jersey sizes, position/role
   - Hackathon: team name, project idea, tech stack, GitHub profile
   - Workshop: experience level, laptop availability, preferred language
   - Conference: company, job title, dietary preference, accessibility needs
   - Cultural fest: performance type, group size, song/act title
   - Marathon/Run: t-shirt size, emergency contact, medical conditions
   
   For each custom field, determine:
   - The field type (text, select, radio, textarea, number, player_names)
   - Whether it's required or optional
   - If it's a select/radio, what are the options?
   - If it's player_names, how many players?

Rules:
- Ask 1-2 focused questions at a time, never dump all questions at once
- Be friendly and professional
- If user provides vague answers, ask for specifics
- Once ALL details are gathered and confirmed, reply ONLY with the word: FINALIZE_PLAN"""

    if template:
        required = "\n".join(f"  - {f}" for f in template.get("required_fields", []))
        base += f"""

This is a **{template['name']}** event. You have pre-filled context for this event type.
Make sure to specifically collect these details for a {template['event_type']}:
{required}

Start by confirming the event name and date, then gather the specifics above."""

    return base


PLAN_GENERATION_PROMPT = """Given the conversation history AND the provided Reference Documents (from the Organizer's Knowledge Base), output a structured JSON plan for the event.
Use the Reference Documents to fill in specific rules, coordinator names, or schedules that the user might have uploaded as PDFs.

Always respond with VALID JSON only, no markdown fences.
The JSON must have this exact schema:
{
  "event_name": string,
  "event_type": string,
  "date": string,
  "venue": string,
  "theme": string,
  "description": string,
  "total_participants_expected": number,
  "schedule": [
    {
      "time": "HH:MM",
      "duration_mins": number,
      "activity": string,
      "location": string,
      "coordinator": string,
      "notes": string
    }
  ],
  "activities": [
    {
      "name": string,
      "description": string,
      "max_participants": number,
      "prizes": string
    }
  ],
  "resources": {
    "rooms": [string],
    "equipment": [string],
    "volunteers_needed": number,
    "budget_estimate_inr": number
  },
  "rules": [string],
  "judging_criteria": [string],
  "sponsors_target": [string],
  "custom_registration_fields": [
    {
      "field_name": string,
      "display_label": string,
      "field_type": string,
      "required": boolean,
      "options": [string],
      "count": number
    }
  ]
}"""


# ─── API-Friendly Chat (stateless — history passed in) ───────────────────────

def architect_chat(
    message: str,
    history: list[dict],
    template_id: str | None = None,
) -> dict:
    """
    Stateless single-turn chat for the API/Dashboard.

    Args:
        message: Latest user message
        history: Full conversation history [{role, content}, ...]
        template_id: Optional template ID to inject context

    Returns:
        {
          "reply": str,           # assistant message to show user
          "finalized": bool,      # True when LLM says FINALIZE_PLAN
          "plan": dict | None,    # structured plan (only when finalized)
          "history": list         # updated history to pass back next turn
        }
    """
    template = get_template_by_id(template_id) if template_id else None
    system_prompt = _build_system_prompt(template)

    # Build message list
    messages = [{"role": "system", "content": system_prompt}]

    # Inject template context as first assistant message if history is empty
    if not history and template:
        default_sched_str = json.dumps(template.get("default_schedule", []), indent=2)
        custom_hints = json.dumps(template.get("custom_registration_fields_hint", []), indent=2)
        template_context = (
            f"I'm using the **{template['name']}** template to help you. "
            f"This pre-loads a default schedule and suggested registration fields.\n\n"
            f"Default Schedule:\n```json\n{default_sched_str}\n```\n\n"
            f"Suggested Registration Fields:\n```json\n{custom_hints}\n```\n\n"
            f"You can customize everything. Now let's start — what's the name of your event and when is it?"
        )
        first_reply = {"role": "assistant", "content": template_context}
        history = [first_reply]
        return {
            "reply": template_context,
            "finalized": False,
            "plan": None,
            "history": history,
        }

    # Rebuild full context
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=800,
    )
    ai_reply = response.choices[0].message.content.strip()

    # Check if architect is done
    if "FINALIZE_PLAN" in ai_reply:
        plan = _generate_plan(messages + [{"role": "user", "content": message}], template)
        updated_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": "✅ All information gathered! Generating your complete event plan..."},
        ]
        return {
            "reply": "✅ Perfect! I have all the information needed. Generating your complete event plan now...",
            "finalized": True,
            "plan": plan,
            "history": updated_history,
        }

    updated_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ai_reply},
    ]
    return {
        "reply": ai_reply,
        "finalized": False,
        "plan": None,
        "history": updated_history,
    }


def _generate_plan(messages: list[dict], template: dict | None = None) -> dict:
    """Internal: generate the final JSON plan from conversation history."""
    print("[Architect] Searching Organizer Knowledge Base for uploaded PDFs...")
    conv_text = " ".join([m["content"] for m in messages if m["role"] == "user"])

    kb_context = ""
    try:
        from tools.embedding_tool import get_embedding
        from tools.supabase_tool import _client as _sb
        query_vec = get_embedding(conv_text)
        res = _sb().rpc("search_knowledge_base", {
            "query_embedding": query_vec,
            "match_threshold": 0.5,
            "match_count": 5
        }).execute()
        if res.data:
            print(f"  -> Found {len(res.data)} relevant snippets in Knowledge Base!")
            kb_context = "\n\n--- REFERENCE DOCUMENTS ---\n"
            for row in res.data:
                kb_context += f"- {row['content']}\n"
    except Exception as e:
        print(f"  -> Skipping KB Search: {e}")

    # Inject template defaults into plan prompt
    template_hint = ""
    if template:
        template_hint = f"\n\nThis is a {template['event_type']} event. Use template defaults where user hasn't overridden:\n"
        template_hint += f"Default schedule (use as fallback): {json.dumps(template.get('default_schedule', []))}\n"
        template_hint += f"Suggested custom fields: {json.dumps(template.get('custom_registration_fields_hint', []))}"

    final_prompt = PLAN_GENERATION_PROMPT + template_hint
    if kb_context:
        final_prompt += kb_context

    gen_messages = list(messages)
    gen_messages.append({"role": "system", "content": final_prompt})

    json_response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=gen_messages,
        temperature=0.2,
        max_tokens=4000,
    )

    raw = json_response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    try:
        plan = json.loads(raw)
        # Normalize plan structure if LLM double-nested it (e.g. {"plan": {"plan": {...}}})
        while "plan" in plan and isinstance(plan["plan"], dict) and "event_name" not in plan:
            plan = plan["plan"]
    except json.JSONDecodeError as e:
        print(f"[Architect] JSON decode error: {e}")
        return {}

    out_path = OUTPUTS_DIR / "schedule.json"
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[Architect] ✅ Full event plan saved → {out_path}")
    return plan


# ─── Legacy Interactive CLI ───────────────────────────────────────────────────

def generate_event_plan(initial_prompt: str = "") -> dict:
    """
    Legacy CLI: interactive session via stdin/stdout.
    """
    print(f"\n[Architect] Starting interactive planning session...")

    # Show templates
    print(get_templates_summary())
    tpl_input = input("Enter template ID (or press Enter to start blank): ").strip().lower()
    template = get_template_by_id(tpl_input) if tpl_input else None

    if template:
        print(f"\n✅ Using template: {template['icon']} {template['name']}")

    print(f"\nType your responses. Type 'quit' to exit.\n")

    system_prompt = _build_system_prompt(template)
    messages = [{"role": "system", "content": system_prompt}]

    context = f"Base Context → Event Name: {EVENT_NAME}, Date: {EVENT_DATE}, Venue: {EVENT_VENUE}."
    if initial_prompt:
        context += f"\nUser initial prompt: {initial_prompt}"
    if template:
        context += f"\nTemplate selected: {template['name']} ({template['event_type']})"

    messages.append({"role": "user", "content": context})

    while True:
        response = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )
        ai_reply = response.choices[0].message.content.strip()

        if "FINALIZE_PLAN" in ai_reply:
            print("\n[Architect] Information gathered! Generating the final JSON plan...")
            break

        print(f"\n🤖 Architect: {ai_reply}")
        messages.append({"role": "assistant", "content": ai_reply})

        user_input = input("🗣️  You: ").strip()
        if user_input.lower() in ['quit', 'exit', 'stop']:
            print("Planning cancelled.")
            return {}

        messages.append({"role": "user", "content": user_input})

    plan = _generate_plan(messages, template)
    return plan


def display_plan_summary(plan: dict) -> str:
    """Returns a human-readable summary of the generated plan."""
    lines = [
        f"📅 {plan.get('event_name')} — {plan.get('event_type')}",
        f"📍 {plan.get('venue')} | {plan.get('date')}",
        f"🎨 Theme: {plan.get('theme')}",
        f"👥 Expected: {plan.get('total_participants_expected')} participants",
        "",
        "📋 SCHEDULE:",
    ]
    for slot in plan.get("schedule", []):
        lines.append(f"  {slot['time']} ({slot['duration_mins']}min) — {slot['activity']} @ {slot['location']}")
    lines.append("\n🏆 ACTIVITIES:")
    for act in plan.get("activities", []):
        lines.append(f"  • {act['name']}: {act['description']} (Max: {act['max_participants']})")
    lines.append("")

    custom_fields = plan.get("custom_registration_fields", [])
    if custom_fields:
        lines.append("📝 CUSTOM REGISTRATION FIELDS:")
        for field in custom_fields:
            opts = f" (Options: {', '.join(field['options'])})" if field.get("options") else ""
            lines.append(f"  • {field['display_label']} [{field['field_type']}]{opts}")
        lines.append("")

    res = plan.get("resources", {})
    lines.append("📋 RESOURCES:")
    lines.append(f"  🏢 Rooms: {', '.join(res.get('rooms', []))}")
    lines.append(f"  👷 Volunteers needed: {res.get('volunteers_needed')}")
    lines.append(f"  💰 Budget estimate: ₹{res.get('budget_estimate_inr', 0):,}")

    sponsors = plan.get("sponsors_target", [])
    if sponsors:
        lines.append(f"\n🤝 Sponsor Targets: {', '.join(sponsors[:5])}")

    return "\n".join(lines)


if __name__ == "__main__":
    plan = generate_event_plan()
    if plan:
        print("\n" + display_plan_summary(plan))
