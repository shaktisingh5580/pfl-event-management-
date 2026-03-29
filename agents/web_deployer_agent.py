"""
agents/web_deployer_agent.py
Web Deployer — generates a React static event website via LLM,
pushes it to a new GitHub repo, and deploys it to Vercel automatically.

Pipeline:
  1. LLM generates all HTML/CSS/JS files for the event site
  2. GitHub REST API → create repo → push files
  3. Vercel REST API → create project (linked to GitHub) → trigger deploy → poll for live URL
  4. Write LIVE URL back to .env as EVENT_WEBSITE_URL
"""

import re
import json
import time
import base64
import pathlib
import textwrap
import requests
from openai import OpenAI

from config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    GITHUB_TOKEN, GITHUB_USERNAME,
    VERCEL_TOKEN, VERCEL_TEAM_ID,
    SUPABASE_URL, SUPABASE_ANON_KEY,
    EVENT_NAME, EVENT_DATE, EVENT_VENUE, EVENT_HASHTAG,
    OUTPUTS_DIR, BASE_DIR,
)

# ── helpers ────────────────────────────────────────────────────────────────

_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def _slug(name: str) -> str:
    """Convert event name to a GitHub-safe lowercase slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:50] or "event-site"


def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _vercel_headers() -> dict:
    return {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }


def _b64(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode()


# ── Step 1: Generate site files via LLM ────────────────────────────────────

def generate_site_files(plan: dict) -> dict:
    """
    Ask LLM to generate the complete static React site.
    Returns dict of { filename: file_content }.
    """
    print("[WebDeployer] 🤖 Generating site files via LLM...")

    schedule_text = "\n".join(
        f"  {s['time']} — {s['activity']} @ {s.get('location','')}"
        for s in plan.get("schedule", [])
    )
    activities_text = "\n".join(
        f"  • {a['name']}: {a['description']} | Prizes: {a.get('prizes','TBD')} | Max: {a.get('max_participants','?')}"
        for a in plan.get("activities", [])
    )
    
    custom_fields_text = ""
    custom_fields = plan.get("custom_registration_fields", [])
    if custom_fields:
        lines = []
        for field in custom_fields:
            opts = f" (Options: {', '.join(field['options'])})" if field.get('options') else ""
            lines.append(f" - Field Label: {field['display_label']}, JSON Key: {field['field_name']}, Type: {field['field_type']}{opts}")
        custom_fields_text = "\n".join(lines)
    else:
        custom_fields_text = "No custom fields requested."

    default_schedule = "  09:00 — Opening Ceremony @ Main Hall\n  17:00 — Closing Ceremony @ Main Hall"
    default_activities = "  \u2022 Hackathon: Build something amazing | Prizes: TBD | Max: 50"

    # ── Exact Supabase registration snippet the LLM MUST replicate ────────────
    _SUPABASE_REG_SNIPPET = f"""
// EXACT Supabase registration — copy this pattern:
const SUPABASE_URL = "{SUPABASE_URL}";
const SUPABASE_KEY = "{SUPABASE_ANON_KEY}";
async function registerAttendee(payload) {{
  const res = await fetch(SUPABASE_URL + "/rest/v1/attendees", {{
    method: "POST",
    headers: {{
      "apikey": SUPABASE_KEY,
      "Authorization": "Bearer " + SUPABASE_KEY,
      "Content-Type": "application/json",
      "Prefer": "return=minimal"
    }},
    body: JSON.stringify(payload)
  }});
  if (res.status === 409) throw new Error("already_registered");
  if (!res.ok) throw new Error(await res.text());
}}
// Required payload fields (match attendees table exactly):
// name, email, phone, college, year_of_study, department,
// telegram_username, skills, interests, goals, team_preference,
// password_hash (this will be the plain text password from the form, the DB trigger hashes it),
// dynamic_fields (JSON object mapping), checked_in (false), source ("website")
"""

    system_prompt = textwrap.dedent(f"""
You are a senior frontend engineer. Generate a COMPLETE multi-page static event website.

OUTPUT FORMAT: Return ONLY valid JSON — no markdown fences, no explanation:
{{"files": {{"index.html": "...", "wall.html": "...", "verify.html": "...", "style.css": "..."}}}}

TECH STACK (required):
- Tailwind CSS via CDN: <script src="https://cdn.tailwindcss.com"></script>
- Google Fonts Inter: <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap">
- Vanilla JS only — NO React, NO import/export
- All JS in plain <script> tags

DESIGN (required):
- Dark theme: background #07070f, glassmorphism cards (rgba white 3-5%, backdrop-filter blur)
- Purple-to-blue gradient accent: #a855f7 → #3b82f6
- Smooth animations: fadeUp on hero, hover lifts on cards
- Mobile responsive with Tailwind breakpoints

index.html MUST contain (in order):
1. Fixed glassmorphism navbar with event name + nav links + CTA button
2. Hero section: big event name, theme subtitle, date/venue/participants, live countdown timer (JS), two CTA buttons
3. Stats bar: prize pool, participant count, event count
4. Schedule section: glassmorphism table with time/activity/location columns
5. Activities section: grid of cards each with icon, name, description, prize badge, team size badge
6. Registration form (use EXACT Supabase fetch pattern below)
7. Footer with links to wall.html and verify.html

REGISTRATION FORM fields (all required in payload to Supabase):
name*, email*, password_hash* (Label as Password, type="password"), phone*, college*, year_of_study* (select: FY/SY/TY/LY/PG),
department* (select: CE/IT/EC/EE/ME/Other), telegram_username,
skills, interests, goals, team_preference (radio: solo/have_team/looking_for_team)

**CUSTOM REQUIRED DYNAMIC FIELDS**:
The user requested these custom fields. You MUST add them as inputs/selects on the registration form.
{custom_fields_text}

When submitting the form, all standard fields go at the root of the JSON payload.
All custom dynamic fields MUST be nested inside a single `dynamic_fields` JSON object.

Example Payload:
{{
  "name": "John Doe",
  "email": "john@example.com",
  ... standard fields ...
  "dynamic_fields": {{
     "tshirt_size": "M",
     "dietary_pref": "Vegan"
  }}
}}

{_SUPABASE_REG_SNIPPET}

{_SUPABASE_REG_SNIPPET}

Registration success: show green box with "Registration successful. Redirecting to your dashboard..." and then use `window.location.href = "/login"` after 3 seconds.
Registration duplicate (HTTP 409 or code 23505): show blue "already registered" box with a link to /login
Registration error: show red error box

wall.html: dark fullscreen grid, polls /rest/v1/wall_photos?status=eq.approved every 5s, shows photo grid with sender name overlay, empty state with emoji placeholder

verify.html: auto-reads ?id= from URL, queries /rest/v1/certificates?cert_id=eq.ID, shows green verified card or red not-found card

style.css: CSS custom properties for colors, smooth scroll, box-sizing reset
""").strip()

    user_prompt = textwrap.dedent(f"""
Event Name: {plan.get('event_name', EVENT_NAME)}
Event Type: {plan.get('event_type', 'Tech Fest')}
Date: {plan.get('date', EVENT_DATE)}
Venue: {plan.get('venue', EVENT_VENUE)}
Theme: {plan.get('theme', 'Technology & Innovation')}
Description: {plan.get('description', 'An amazing tech event.')}
Hashtag: {EVENT_HASHTAG}
Expected participants: {plan.get('total_participants_expected', 200)}

Schedule:
{schedule_text or default_schedule}

Activities:
{activities_text or default_activities}

Supabase URL: {SUPABASE_URL}
Supabase Anon Key: {SUPABASE_ANON_KEY}

Now generate the complete website JSON. Make it visually stunning.
""").strip()

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=12000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if any
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        data = json.loads(raw)
        files: dict = data.get("files", {})
    except json.JSONDecodeError:
        # Fallback: build a minimal site ourselves
        print("[WebDeployer] ⚠️  LLM response wasn't valid JSON — using built-in template.")
        files = _builtin_site(plan)

    # Always add vercel.json for clean routing
    files["vercel.json"] = json.dumps({
        "rewrites": [{"source": "/(.*)", "destination": "/$1"}],
        "headers": [{"source": "/(.*)", "headers": [{"key": "Cache-Control", "value": "no-cache"}]}]
    }, indent=2)

    # Add a simple README
    files["README.md"] = (
        f"# {plan.get('event_name', EVENT_NAME)} — Event Website\n\n"
        f"Auto-generated by the AI Event Management System.\n\n"
        f"**Date:** {plan.get('date', EVENT_DATE)}  \n"
        f"**Venue:** {plan.get('venue', EVENT_VENUE)}  \n"
        f"**Hashtag:** {EVENT_HASHTAG}\n"
    )

    print(f"[WebDeployer] ✅ Generated {len(files)} files: {list(files.keys())}")
    return files


def _build_dynamic_form_fields_html(custom_fields: list[dict]) -> str:
    """Generate HTML form field elements from custom_registration_fields."""
    if not custom_fields:
        return ""
    
    html_parts = []
    html_parts.append('\n        <!-- CUSTOM DYNAMIC FIELDS -->')
    html_parts.append('        <div class="border-t border-white/10 pt-5 mt-5">')
    html_parts.append('          <p class="text-purple-400 text-sm font-semibold mb-4">📋 Event-Specific Information</p>')
    
    for field in custom_fields:
        fname = field.get("field_name", "custom")
        label = field.get("display_label", fname)
        ftype = field.get("field_type", "text")
        options = field.get("options", [])
        required = field.get("required", False)
        req_attr = ' required' if required else ''
        req_star = ' *' if required else ''
        field_id = f'f-dyn-{fname}'
        
        if ftype == "select" and options:
            opts_html = ''.join(f'<option value="{o}">{o}</option>' for o in options)
            html_parts.append(f'''
          <div>
            <label class="block text-sm text-gray-400 mb-1">{label}{req_star}</label>
            <select id="{field_id}" class="w-full rounded-xl px-4 py-3 bg-white/5 border border-white/12 text-gray-200"{req_attr}>
              <option value="">Select...</option>
              {opts_html}
            </select>
          </div>''')
        elif ftype == "textarea":
            html_parts.append(f'''
          <div>
            <label class="block text-sm text-gray-400 mb-1">{label}{req_star}</label>
            <textarea id="{field_id}" class="w-full rounded-xl px-4 py-3 h-24 resize-none bg-white/5 border border-white/12 text-gray-200" placeholder="{label}"{req_attr}></textarea>
          </div>''')
        elif ftype == "radio" and options:
            radios = ''.join(
                f'<label class="flex items-center gap-2 text-gray-300 text-sm">'
                f'<input type="radio" name="{fname}" value="{o}" class="accent-purple-500"> {o}</label>'
                for o in options
            )
            html_parts.append(f'''
          <div>
            <label class="block text-sm text-gray-400 mb-1">{label}{req_star}</label>
            <div class="flex flex-wrap gap-4 mt-1">{radios}</div>
          </div>''')
        elif ftype == "number":
            html_parts.append(f'''
          <div>
            <label class="block text-sm text-gray-400 mb-1">{label}{req_star}</label>
            <input type="number" id="{field_id}" class="w-full rounded-xl px-4 py-3 bg-white/5 border border-white/12 text-gray-200" placeholder="{label}"{req_attr}>
          </div>''')
        elif ftype == "player_names":
            # Special multi-input field for team sports (e.g. 11 player names)
            count = field.get("count", 11)
            inputs = ''.join(
                f'<input type="text" class="dyn-player-{fname} w-full rounded-xl px-4 py-3 bg-white/5 border border-white/12 text-gray-200 mb-2" '
                f'placeholder="Player {i+1} name"{req_attr}>'
                for i in range(count)
            )
            html_parts.append(f'''
          <div>
            <label class="block text-sm text-gray-400 mb-1">{label}{req_star} ({count} players)</label>
            {inputs}
          </div>''')
        else:
            # Default: text input
            html_parts.append(f'''
          <div>
            <label class="block text-sm text-gray-400 mb-1">{label}{req_star}</label>
            <input type="{ftype}" id="{field_id}" class="w-full rounded-xl px-4 py-3 bg-white/5 border border-white/12 text-gray-200" placeholder="{label}"{req_attr}>
          </div>''')
    
    html_parts.append('        </div>')
    return '\n'.join(html_parts)


def _build_dynamic_fields_js(custom_fields: list[dict]) -> str:
    """Generate JavaScript to collect dynamic field values into a dynamic_fields object."""
    if not custom_fields:
        return '      const dynamic_fields = {};'
    
    lines = ['      const dynamic_fields = {};']
    for field in custom_fields:
        fname = field.get("field_name", "custom")
        ftype = field.get("field_type", "text")
        field_id = f'f-dyn-{fname}'
        
        if ftype == "radio":
            lines.append(
                f'      {{ const r = document.querySelector(\'input[name="{fname}"]:checked\');'
                f' if (r) dynamic_fields["{fname}"] = r.value; }}'
            )
        elif ftype == "player_names":
            lines.append(
                f'      dynamic_fields["{fname}"] = Array.from(document.querySelectorAll(\'.dyn-player-{fname}\')).map(el => el.value).filter(v => v.trim());'
            )
        else:
            lines.append(
                f'      {{ const el = document.getElementById("{field_id}"); if (el) dynamic_fields["{fname}"] = el.value; }}'
            )
    
    return '\n'.join(lines)


def _builtin_site(plan: dict) -> dict:
    """High-quality built-in template used as fallback if LLM fails."""
    event_name   = plan.get("event_name", EVENT_NAME)
    event_date   = plan.get("date", EVENT_DATE)
    event_venue  = plan.get("venue", EVENT_VENUE)
    event_theme  = plan.get("theme", "Technology & Innovation")
    description  = plan.get("description", "Join us for an amazing event!")
    participants = plan.get("total_participants_expected", 200)
    custom_fields = plan.get("custom_registration_fields", [])

    schedule_rows = "".join(
        f'<tr><td class="py-3 px-4 text-purple-300 font-mono">{s["time"]}</td>'
        f'<td class="py-3 px-4 font-semibold">{s["activity"]}</td>'
        f'<td class="py-3 px-4 text-gray-400">{s.get("location","")}</td></tr>'
        for s in plan.get("schedule", [])
    )

    activity_cards = "".join(
        f'<div class="glass-card p-6 rounded-2xl">'
        f'<h3 class="text-xl font-bold text-purple-300 mb-2">{a["name"]}</h3>'
        f'<p class="text-gray-300 mb-3">{a["description"]}</p>'
        f'<div class="flex gap-4 text-sm">'
        f'<span class="bg-purple-900/50 px-3 py-1 rounded-full">🏆 {a.get("prizes","TBD")}</span>'
        f'<span class="bg-blue-900/50 px-3 py-1 rounded-full">👥 Max {a.get("max_participants","?")}</span>'
        f'</div></div>'
        for a in plan.get("activities", [])
    )

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{event_name}</title>
  <meta name="description" content="{description}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
  <link href="style.css" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: 'Inter', sans-serif; background: #0a0a0f; color: #e2e8f0; }}
    .glass-card {{ background: rgba(255,255,255,0.04); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); }}
    .gradient-text {{ background: linear-gradient(135deg, #a855f7, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .hero-bg {{ background: radial-gradient(ellipse at 50% 0%, rgba(168,85,247,0.15) 0%, transparent 70%); }}
    .count-box {{ background: rgba(168,85,247,0.15); border: 1px solid rgba(168,85,247,0.3); }}
    input, textarea {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; }}
    input:focus, textarea:focus {{ outline: none; border-color: #a855f7; }}
  </style>
</head>
<body>
  <!-- NAV -->
  <nav class="fixed top-0 left-0 right-0 z-50 glass-card px-6 py-4 flex justify-between items-center">
    <span class="font-black text-xl gradient-text">{event_name}</span>
    <div class="flex gap-6 text-sm text-gray-300">
      <a href="#schedule" class="hover:text-purple-400 transition">Schedule</a>
      <a href="#activities" class="hover:text-purple-400 transition">Activities</a>
      <a href="#register" class="hover:text-purple-400 transition">Register</a>
      <a href="wall.html" class="hover:text-purple-400 transition">Social Wall</a>
    </div>
  </nav>

  <!-- HERO -->
  <section class="hero-bg min-h-screen flex flex-col items-center justify-center text-center pt-24 px-4">
    <div class="inline-block bg-purple-900/30 border border-purple-700/40 rounded-full px-4 py-1 text-purple-300 text-sm mb-6">
      {EVENT_HASHTAG}
    </div>
    <h1 class="text-6xl md:text-8xl font-black gradient-text mb-4">{event_name}</h1>
    <p class="text-xl text-blue-300 font-semibold mb-2">{event_theme}</p>
    <p class="text-gray-400 max-w-xl mb-4">{description}</p>
    <p class="text-gray-300 mb-10">
      📅 <strong>{event_date}</strong> &nbsp;|&nbsp; 📍 <strong>{event_venue}</strong>
      &nbsp;|&nbsp; 👥 <strong>{participants}+ participants</strong>
    </p>

    <!-- COUNTDOWN -->
    <div class="flex gap-4 mb-10" id="countdown">
      <div class="count-box rounded-2xl px-6 py-4 text-center">
        <div class="text-4xl font-black text-purple-300" id="cd-d">00</div>
        <div class="text-xs text-gray-500 uppercase tracking-widest">Days</div>
      </div>
      <div class="count-box rounded-2xl px-6 py-4 text-center">
        <div class="text-4xl font-black text-blue-300" id="cd-h">00</div>
        <div class="text-xs text-gray-500 uppercase tracking-widest">Hours</div>
      </div>
      <div class="count-box rounded-2xl px-6 py-4 text-center">
        <div class="text-4xl font-black text-purple-300" id="cd-m">00</div>
        <div class="text-xs text-gray-500 uppercase tracking-widest">Mins</div>
      </div>
      <div class="count-box rounded-2xl px-6 py-4 text-center">
        <div class="text-4xl font-black text-blue-300" id="cd-s">00</div>
        <div class="text-xs text-gray-500 uppercase tracking-widest">Secs</div>
      </div>
    </div>
    <a href="#register" class="bg-purple-600 hover:bg-purple-500 transition px-8 py-3 rounded-full font-bold text-white shadow-lg shadow-purple-900/50">
      Register Now →
    </a>
  </section>

  <!-- SCHEDULE -->
  <section id="schedule" class="max-w-4xl mx-auto px-4 py-24">
    <h2 class="text-4xl font-black gradient-text mb-10 text-center">📋 Event Schedule</h2>
    <div class="glass-card rounded-2xl overflow-hidden">
      <table class="w-full">
        <thead><tr class="border-b border-white/10">
          <th class="py-3 px-4 text-left text-purple-400 text-sm uppercase">Time</th>
          <th class="py-3 px-4 text-left text-purple-400 text-sm uppercase">Activity</th>
          <th class="py-3 px-4 text-left text-purple-400 text-sm uppercase">Location</th>
        </tr></thead>
        <tbody class="divide-y divide-white/5">{schedule_rows}</tbody>
      </table>
    </div>
  </section>

  <!-- ACTIVITIES -->
  <section id="activities" class="max-w-5xl mx-auto px-4 py-12">
    <h2 class="text-4xl font-black gradient-text mb-10 text-center">🏆 Activities & Competitions</h2>
    <div class="grid md:grid-cols-2 gap-6">{activity_cards}</div>
  </section>

  <!-- REGISTER -->
  <section id="register" class="max-w-xl mx-auto px-4 py-24">
    <h2 class="text-4xl font-black gradient-text mb-2 text-center">✍️ Register Now</h2>
    <p class="text-gray-400 text-center mb-10">Secure your spot at {event_name}</p>
    <div class="glass-card rounded-3xl p-8">
      <form id="reg-form" class="space-y-5">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Full Name *</label>
          <input type="text" id="f-name" class="w-full rounded-xl px-4 py-3" placeholder="Your name" required>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Email *</label>
          <input type="email" id="f-email" class="w-full rounded-xl px-4 py-3" placeholder="you@example.com" required>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Create a Password *</label>
          <input type="password" id="f-password" class="w-full rounded-xl px-4 py-3" placeholder="For your attendee dashboard" required>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Phone</label>
          <input type="tel" id="f-phone" class="w-full rounded-xl px-4 py-3" placeholder="Your phone number">
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">College / Organization</label>
          <input type="text" id="f-college" class="w-full rounded-xl px-4 py-3" placeholder="Your college name">
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Telegram Username</label>
          <input type="text" id="f-telegram" class="w-full rounded-xl px-4 py-3" placeholder="@yourusername">
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Skills (comma separated)</label>
          <input type="text" id="f-skills" class="w-full rounded-xl px-4 py-3" placeholder="Python, React, ML...">
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Interests</label>
          <textarea id="f-interests" class="w-full rounded-xl px-4 py-3 h-24 resize-none" placeholder="What are you interested in?"></textarea>
        </div>
{_build_dynamic_form_fields_html(custom_fields)}
        <button type="submit" id="reg-btn"
          class="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 transition py-3 rounded-xl font-bold text-white shadow-lg">
          Register for Free
        </button>
        <div id="reg-msg" class="text-center text-sm hidden"></div>
      </form>
    </div>
  </section>

  <!-- FOOTER -->
  <footer class="border-t border-white/5 text-center py-10 text-gray-600 text-sm">
    <p class="gradient-text font-bold text-lg mb-1">{event_name}</p>
    <p>{event_date} · {event_venue} · {EVENT_HASHTAG}</p>
    <p class="mt-4"><a href="wall.html" class="text-purple-500 hover:underline">Social Wall</a> · <a href="verify.html" class="text-purple-500 hover:underline">Verify Certificate</a></p>
  </footer>

  <script>
    // Countdown
    const eventDate = new Date("{event_date}T09:00:00");
    function updateCountdown() {{
      const diff = eventDate - new Date();
      if (diff <= 0) {{ document.getElementById("countdown").innerHTML = '<div class="text-2xl text-purple-300 font-bold">🎉 The event is LIVE!</div>'; return; }}
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      document.getElementById("cd-d").textContent = String(d).padStart(2,"0");
      document.getElementById("cd-h").textContent = String(h).padStart(2,"0");
      document.getElementById("cd-m").textContent = String(m).padStart(2,"0");
      document.getElementById("cd-s").textContent = String(s).padStart(2,"0");
    }}
    setInterval(updateCountdown, 1000);
    updateCountdown();

    // Registration form → Supabase REST API
    const SUPABASE_URL = "{SUPABASE_URL}";
    const SUPABASE_KEY = "{SUPABASE_ANON_KEY}";
    document.getElementById("reg-form").addEventListener("submit", async (e) => {{
      e.preventDefault();
      const btn = document.getElementById("reg-btn");
      const msg = document.getElementById("reg-msg");
      btn.textContent = "Registering..."; btn.disabled = true;

      // Collect dynamic fields
{_build_dynamic_fields_js(custom_fields)}

      const payload = {{
        name: document.getElementById("f-name").value,
        email: document.getElementById("f-email").value,
        password_hash: document.getElementById("f-password").value,
        phone: document.getElementById("f-phone") ? document.getElementById("f-phone").value : "",
        college: document.getElementById("f-college").value,
        telegram_username: document.getElementById("f-telegram") ? document.getElementById("f-telegram").value : "",
        skills: document.getElementById("f-skills").value,
        interests: document.getElementById("f-interests").value,
        dynamic_fields: dynamic_fields,
        source: "website",
        checked_in: false,
        registered_at: new Date().toISOString()
      }};
      try {{
        const res = await fetch(SUPABASE_URL + "/rest/v1/attendees", {{
          method: "POST",
          headers: {{
            "apikey": SUPABASE_KEY,
            "Authorization": "Bearer " + SUPABASE_KEY,
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
          }},
          body: JSON.stringify(payload)
        }});
        if (res.ok || res.status === 201) {{
          msg.textContent = "🎉 Registration successful! Redirecting to your dashboard...";
          msg.className = "text-center text-sm text-green-400"; msg.classList.remove("hidden");
          e.target.reset();
          setTimeout(() => {{ window.location.href = "/login"; }}, 3000);
        }} else if (res.status === 409) {{
          msg.innerHTML = "❌ Already registered. <a href='/login' class='underline'>Log in here</a>";
          msg.className = "text-center text-sm text-blue-400"; msg.classList.remove("hidden");
        }} else {{
          const err = await res.text();
          msg.textContent = "❌ Error: " + err;
          msg.className = "text-center text-sm text-red-400"; msg.classList.remove("hidden");
        }}
      }} catch(err) {{
        msg.textContent = "❌ Network error. Please try again.";
        msg.className = "text-center text-sm text-red-400"; msg.classList.remove("hidden");
      }}
      btn.textContent = "Register for Free"; btn.disabled = false;
    }});
  </script>
</body>
</html>"""

    wall_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{event_name} — Social Wall</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: 'Inter', sans-serif; background: #05050a; color: #e2e8f0; overflow: hidden; }}
    .photo-card {{ transition: all 0.5s ease; animation: fadeIn 0.8s ease-in; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: scale(0.9); }} to {{ opacity: 1; transform: scale(1); }} }}
    .glass {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px); }}
  </style>
</head>
<body class="min-h-screen">
  <div class="fixed top-0 left-0 right-0 z-50 glass px-6 py-3 flex justify-between items-center">
    <span class="font-black text-xl text-purple-400">{event_name} · Social Wall</span>
    <span class="text-sm text-gray-500">{EVENT_HASHTAG} · Live 🔴</span>
  </div>
  <div class="pt-16 p-4" id="wall-grid">
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 min-h-screen" id="photo-grid">
      <div class="col-span-4 flex items-center justify-center h-64 text-gray-600">
        <div class="text-center"><div class="text-6xl mb-4">📸</div><p>Waiting for photos...</p><p class="text-sm mt-2">Send a photo to the Telegram bot with #{EVENT_HASHTAG}</p></div>
      </div>
    </div>
  </div>
  <script>
    const SUPABASE_URL = "{SUPABASE_URL}";
    const SUPABASE_KEY = "{SUPABASE_ANON_KEY}";
    let knownIds = new Set();

    async function fetchPhotos() {{
      try {{
        const res = await fetch(SUPABASE_URL + "/rest/v1/wall_photos?status=eq.approved&order=created_at.desc&limit=20", {{
          headers: {{ "apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY }}
        }});
        if (!res.ok) return;
        const photos = await res.json();
        const grid = document.getElementById("photo-grid");
        let rendered = false;
        for (const photo of photos) {{
          if (!knownIds.has(photo.id)) {{
            knownIds.add(photo.id);
            if (!rendered) {{ grid.innerHTML = ""; rendered = true; }}
            const div = document.createElement("div");
            div.className = "photo-card rounded-2xl overflow-hidden relative aspect-square";
            div.innerHTML = `<img src="${{photo.cloudinary_url}}" class="w-full h-full object-cover" alt="Wall photo">
              <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
                <p class="text-white font-bold text-sm">${{photo.sender_name || "Anonymous"}}</p>
              </div>`;
            grid.prepend(div);
          }}
        }}
      }} catch(e) {{ console.error(e); }}
    }}

    fetchPhotos();
    setInterval(fetchPhotos, 5000);
  </script>
</body>
</html>"""

    verify_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{event_name} — Verify Certificate</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: 'Inter', sans-serif; background: #0a0a0f; color: #e2e8f0; }}
    .glass {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); backdrop-filter: blur(12px); }}
    .gradient-text {{ background: linear-gradient(135deg, #a855f7, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center px-4">
  <div class="w-full max-w-lg">
    <div class="text-center mb-10">
      <a href="index.html" class="text-purple-400 text-sm hover:underline">← Back to {event_name}</a>
      <h1 class="text-4xl font-black gradient-text mt-4 mb-2">Certificate Verification</h1>
      <p class="text-gray-400">Enter a certificate ID or scan a QR code to verify authenticity</p>
    </div>
    <div class="glass rounded-3xl p-8">
      <div class="flex gap-3 mb-6">
        <input type="text" id="cert-id" class="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-purple-500" placeholder="Certificate ID (e.g. CERT-XXXX)">
        <button onclick="verifyCert()" class="bg-purple-600 hover:bg-purple-500 transition px-6 py-3 rounded-xl font-bold">Verify</button>
      </div>
      <div id="result" class="hidden"></div>
    </div>
  </div>
  <script>
    const SUPABASE_URL = "{SUPABASE_URL}";
    const SUPABASE_KEY = "{SUPABASE_ANON_KEY}";

    // Auto-fill from URL ?id=XXXX
    const params = new URLSearchParams(window.location.search);
    if (params.get("id")) {{ document.getElementById("cert-id").value = params.get("id"); verifyCert(); }}

    async function verifyCert() {{
      const id = document.getElementById("cert-id").value.trim();
      const resultDiv = document.getElementById("result");
      if (!id) {{ resultDiv.innerHTML = '<p class="text-red-400">Please enter a certificate ID.</p>'; resultDiv.classList.remove("hidden"); return; }}

      resultDiv.innerHTML = '<p class="text-gray-400 animate-pulse">Verifying...</p>'; resultDiv.classList.remove("hidden");

      try {{
        const res = await fetch(SUPABASE_URL + "/rest/v1/certificates?cert_id=eq." + encodeURIComponent(id) + "&select=*", {{
          headers: {{ "apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY }}
        }});
        const certs = await res.json();
        if (certs.length > 0) {{
          const c = certs[0];
          resultDiv.innerHTML = `
            <div class="bg-green-900/30 border border-green-700/40 rounded-2xl p-6 text-center">
              <div class="text-5xl mb-4">✅</div>
              <h3 class="text-green-400 font-black text-2xl mb-1">Certificate Verified!</h3>
              <p class="text-gray-300 text-lg font-semibold">${{c.attendee_name}}</p>
              <p class="text-purple-300">${{c.rank || "Participant"}}</p>
              <p class="text-gray-500 text-sm mt-3">{event_name} · ${{c.issued_at ? new Date(c.issued_at).toLocaleDateString() : '{event_date}' }}</p>
            </div>`;
        }} else {{
          resultDiv.innerHTML = `
            <div class="bg-red-900/30 border border-red-700/40 rounded-2xl p-6 text-center">
              <div class="text-5xl mb-4">❌</div>
              <h3 class="text-red-400 font-black text-xl">Certificate Not Found</h3>
              <p class="text-gray-400 mt-2">No certificate with ID: ${{id}}</p>
            </div>`;
        }}
      }} catch(e) {{
        resultDiv.innerHTML = '<p class="text-red-400">Network error. Please try again.</p>';
      }}
    }}
  </script>
</body>
</html>"""

    style_css = """:root {
  --color-bg: #0a0a0f;
  --color-purple: #a855f7;
  --color-blue: #3b82f6;
  --color-card: rgba(255,255,255,0.04);
  --color-border: rgba(255,255,255,0.08);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body { font-family: 'Inter', sans-serif; background: var(--color-bg); color: #e2e8f0; }
a { color: inherit; text-decoration: none; }
section { scroll-margin-top: 80px; }
"""
    return {
        "index.html": index_html,
        "wall.html": wall_html,
        "verify.html": verify_html,
        "style.css": style_css,
    }


# ── Step 2: Create GitHub repo ──────────────────────────────────────────────

def create_github_repo(slug: str) -> str:
    """
    Creates a public GitHub repo '{GITHUB_USERNAME}/{slug}'.
    Returns 'owner/repo' full name string.
    Skips if repo already exists.
    """
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN not set in .env")

    url  = "https://api.github.com/user/repos"
    body = {
        "name": slug,
        "description": f"Auto-generated event website for {EVENT_NAME}",
        "private": False,
        "auto_init": False,
    }
    r = requests.post(url, json=body, headers=_gh_headers(), timeout=30)

    if r.status_code == 422:
        # Repo already exists — that's fine
        full_name = f"{GITHUB_USERNAME}/{slug}"
        print(f"[WebDeployer] ℹ️  Repo already exists: {full_name}")
        return full_name
    elif r.status_code not in (200, 201):
        print(f"[WebDeployer] ⚠️ GitHub repo creation failed {r.status_code}: {r.text[:100]}")
        print("[WebDeployer] ⚠️ Proceeding with direct Vercel deployment without GitHub mapping.")
        return f"{GITHUB_USERNAME or 'local'}/{slug}"

    full_name = r.json().get("full_name", f"{GITHUB_USERNAME}/{slug}")
    print(f"[WebDeployer] ✅ Created GitHub repo: https://github.com/{full_name}")
    return full_name


# ── Step 3: Push files to GitHub ───────────────────────────────────────────

def push_files_to_github(full_name: str, files: dict) -> None:
    """Push each file in `files` dict to the GitHub repo via Contents API."""
    print(f"[WebDeployer] 📤 Pushing {len(files)} files to GitHub...")

    for filename, content in files.items():
        url = f"https://api.github.com/repos/{full_name}/contents/{filename}"

        # Check if file already exists (get its SHA for updates)
        sha = None
        existing = requests.get(url, headers=_gh_headers(), timeout=15)
        if existing.status_code == 200:
            sha = existing.json().get("sha")

        body = {
            "message": f"{'Update' if sha else 'Add'} {filename} via AI Event System",
            "content": _b64(content),
        }
        if sha:
            body["sha"] = sha

        r = requests.put(url, json=body, headers=_gh_headers(), timeout=30)
        if r.status_code not in (200, 201):
            print(f"[WebDeployer] ⚠️  Failed to push {filename}: {r.status_code} {r.text[:200]}")
        else:
            print(f"[WebDeployer]   ✓ {filename}")

    print(f"[WebDeployer] ✅ All files pushed → https://github.com/{full_name}")


# ── Step 4: Deploy to Vercel (direct file-upload — no GitHub OAuth needed) ─

import hashlib

def _sha1(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()


def deploy_to_vercel(full_name: str, slug: str, files: dict = None) -> str:
    """
    Deploys site files directly to Vercel using the file-upload API.
    This approach works with just VERCEL_TOKEN — no GitHub OAuth/webhook setup.
    Falls back gracefully if VERCEL_TOKEN is not set.

    Args:
        full_name: GitHub repo full_name (used only for display/fallback message)
        slug:      Vercel project name slug
        files:     dict of {filename: content}. If None, loads from outputs/website/
    """
    if not VERCEL_TOKEN or VERCEL_TOKEN.startswith("xxx"):
        github_url = f"https://github.com/{full_name}"
        print(
            "\n[WebDeployer] ⚠️  VERCEL_TOKEN not set — skipping auto-deploy.\n"
            f"  To deploy manually:\n"
            f"  1. Go to https://vercel.com/new\n"
            f"  2. Import: {github_url}\n"
            f"  3. Deploy — it's a static site, no build step needed."
        )
        return github_url

    # Load files from disk if not passed in
    if files is None:
        local_dir = OUTPUTS_DIR / "website"
        files = {}
        for f in local_dir.iterdir():
            if f.is_file():
                try:
                    files[f.name] = f.read_text(encoding="utf-8")
                except Exception:
                    pass

    base = "https://api.vercel.com"
    team_param = f"?teamId={VERCEL_TEAM_ID.strip()}" if VERCEL_TEAM_ID and VERCEL_TEAM_ID.strip() else ""

    # ─ Step 4a: Upload each file blob ─────────────────────────────────────
    print(f"[WebDeployer] 📦 Uploading {len(files)} files to Vercel...")
    upload_files = []
    for fname, content in files.items():
        sha = _sha1(content)
        encoded = content.encode("utf-8")

        # Upload blob
        up_headers = {
            "Authorization": f"Bearer {VERCEL_TOKEN}",
            "Content-Type": "application/octet-stream",
            "x-vercel-digest": sha,
            "Content-Length": str(len(encoded)),
        }
        r = requests.post(
            f"{base}/v2/files{team_param}",
            data=encoded,
            headers=up_headers,
            timeout=30
        )
        if r.status_code not in (200, 201, 204):
            print(f"[WebDeployer] ⚠️  Upload {fname} → {r.status_code}: {r.text[:120]}")
        else:
            print(f"[WebDeployer]   ✓ uploaded {fname} (sha:{sha[:8]})")

        upload_files.append({
            "file": fname,
            "sha":  sha,
            "size": len(encoded),
        })

    # ─ Step 4b: Create deployment ─────────────────────────────────────────
    print("[WebDeployer] 🚀 Creating Vercel deployment...")
    deploy_body = {
        "name":   slug,
        "files":  upload_files,
        "target": "production",
        "projectSettings": {
            "framework":         None,
            "buildCommand":      None,
            "outputDirectory":   None,
            "installCommand":    None,
            "devCommand":        None,
        },
    }

    dr = requests.post(
        f"{base}/v13/deployments{team_param}",
        json=deploy_body,
        headers=_vercel_headers(),
        timeout=60
    )

    if dr.status_code not in (200, 201):
        print(f"[WebDeployer] ❌ Deployment request failed {dr.status_code}: {dr.text[:400]}")
        # Last-resort fallback: try importing from GitHub
        return _fallback_github_import(full_name, slug, base, team_param)

    deploy_data = dr.json()
    deploy_id   = deploy_data.get("id", "")
    deploy_url  = deploy_data.get("url", "")
    live_url    = f"https://{deploy_url}" if deploy_url and not deploy_url.startswith("http") else deploy_url or f"https://{slug}.vercel.app"

    print(f"[WebDeployer] ✅ Deployment created: {deploy_id}")

    # ─ Step 4c: Poll until READY (max 3 minutes) ──────────────────────────
    if deploy_id:
        print(f"[WebDeployer] ⏳ Waiting for deployment to go live...")
        for attempt in range(36):   # 36 × 5s = 3 min
            time.sleep(5)
            sr = requests.get(
                f"{base}/v13/deployments/{deploy_id}{team_param}",
                headers=_vercel_headers(),
                timeout=15
            )
            if sr.ok:
                d = sr.json()
                state = d.get("readyState", d.get("status", ""))
                print(f"[WebDeployer]   [{attempt+1:02d}/36] state={state}")
                if state in ("READY", "ready"):
                    live_url = "https://" + (d.get("url") or slug + ".vercel.app")
                    break
                elif state in ("ERROR", "CANCELED", "FAILED"):
                    err_msg = d.get("errorMessage", "unknown error")
                    print(f"[WebDeployer] ❌ Deployment {state}: {err_msg}")
                    break
            else:
                print(f"[WebDeployer]   poll {attempt+1}: HTTP {sr.status_code}")

    return live_url


def _fallback_github_import(full_name: str, slug: str, base: str, team_param: str) -> str:
    """Last-resort: create a Vercel project linked to GitHub and let the webhook trigger a build."""
    print("[WebDeployer] 🔄 Attempting GitHub-linked project as fallback...")
    proj_body = {
        "name": slug,
        "gitRepository": {"type": "github", "repo": full_name},
        "framework": None,
    }
    r = requests.post(f"{base}/v10/projects{team_param}", json=proj_body, headers=_vercel_headers(), timeout=30)
    if r.status_code in (200, 201, 409):
        live_url = f"https://{slug}.vercel.app"
        print(f"[WebDeployer] ✅ Project created — GitHub webhook will trigger deploy")
        print(f"[WebDeployer] 🌐 Expected URL: {live_url}")
        return live_url
    print(f"[WebDeployer] ❌ Fallback also failed: {r.status_code} {r.text[:200]}")
    return f"https://github.com/{full_name}"


# ── Step 5: Write URL back to .env ─────────────────────────────────────────

def _update_env_url(live_url: str) -> None:
    """Write the live URL back to .env as EVENT_WEBSITE_URL."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    text = env_path.read_text(encoding="utf-8")
    if "EVENT_WEBSITE_URL=" in text:
        text = re.sub(
            r"EVENT_WEBSITE_URL=.*",
            f"EVENT_WEBSITE_URL={live_url}",
            text
        )
    else:
        text += f"\nEVENT_WEBSITE_URL={live_url}\n"
    env_path.write_text(text, encoding="utf-8")
    print(f"[WebDeployer] ✅ Written EVENT_WEBSITE_URL={live_url} → .env")


# ── Main orchestrator ──────────────────────────────────────────────────────

def run_web_deployer(plan: dict) -> str:
    """
    Full pipeline:
      generate → create GitHub repo → push files → deploy Vercel → update .env
    Returns the live URL.
    """
    print("\n" + "═"*60)
    print("  🌐 WEB DEPLOYER AGENT")
    print("═"*60)

    slug      = _slug(plan.get("event_name", EVENT_NAME))
    print(f"[WebDeployer] Repo slug: {slug}")

    # 1. Generate site
    files = generate_site_files(plan)

    # 2. Save locally too  
    local_dir = OUTPUTS_DIR / "website"
    local_dir.mkdir(exist_ok=True)
    for fname, content in files.items():
        (local_dir / fname).write_text(content, encoding="utf-8")
    print(f"[WebDeployer] 💾 Local copy saved → {local_dir}")

    # 3. GitHub
    full_name = create_github_repo(slug)
    push_files_to_github(full_name, files)

    # 4. Vercel — pass files directly for the file-upload deploy
    live_url = deploy_to_vercel(full_name, slug, files=files)

    # 5. Update .env
    _update_env_url(live_url)

    print("\n" + "═"*60)
    print(f"  ✅ DEPLOYMENT COMPLETE")
    print(f"  🌐 Live URL  : {live_url}")
    print(f"  📦 GitHub    : https://github.com/{full_name}")
    print(f"  📁 Local     : {local_dir}")
    print("═"*60 + "\n")

    return live_url


def redeploy_website() -> str:
    """
    Re-deploys the already-generated website in outputs/website/ to Vercel.
    Does NOT re-run the LLM or re-create the GitHub repo.
    Use this after manually editing the local HTML files.
    """
    print("\n" + "═"*60)
    print("  🔄 REDEPLOY — pushing local files to Vercel")
    print("═"*60)

    local_dir = OUTPUTS_DIR / "website"
    if not local_dir.exists() or not any(local_dir.iterdir()):
        raise RuntimeError(f"No website files found in {local_dir}. Run option [8] first.")

    files = {}
    for f in local_dir.iterdir():
        if f.is_file():
            try:
                files[f.name] = f.read_text(encoding="utf-8")
            except Exception:
                pass

    print(f"[WebDeployer] 📂 Loaded {len(files)} files from {local_dir}")
    slug = _slug(EVENT_NAME)
    full_name = f"{GITHUB_USERNAME}/{slug}"

    # Push updated files to GitHub
    push_files_to_github(full_name, files)

    # Deploy to Vercel directly
    live_url = deploy_to_vercel(full_name, slug, files=files)
    _update_env_url(live_url)

    print("\n" + "═"*60)
    print(f"  ✅ REDEPLOY COMPLETE")
    print(f"  🌐 Live URL  : {live_url}")
    print("═"*60 + "\n")
    return live_url


if __name__ == "__main__":
    import json
    from pathlib import Path
    plan_path = OUTPUTS_DIR / "schedule.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        plan = {
            "event_name": EVENT_NAME,
            "date": EVENT_DATE,
            "venue": EVENT_VENUE,
            "theme": "Technology & Innovation",
            "description": f"Welcome to {EVENT_NAME}!",
            "total_participants_expected": 200,
            "schedule": [],
            "activities": [],
        }
    run_web_deployer(plan)
