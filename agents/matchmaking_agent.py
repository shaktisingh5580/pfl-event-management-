"""
agents/matchmaking_agent.py
Semantic AI Matchmaking — 3-layer pipeline.
Layer 1 (registration): embedding generation + Supabase storage
Layer 2 (database):     match_attendees() SQL RPC with cosine similarity
Layer 3 (active):       proactive Telegram DM with personalized ice-breaker + Accept/Next
"""
from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from tools.embedding_tool import get_embedding, combine_profile_text
from tools.supabase_tool import (
    save_embedding, find_matches, record_match_interaction,
    get_checked_in_attendees, get_attendee_by_id
)


_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


# ─────────────────────────────────────────────────────────────
#  LAYER 1: Embedding on Registration
# ─────────────────────────────────────────────────────────────

def embed_and_store(attendee_id: str, skills: str, interests: str, goals: str) -> list[float]:
    """
    Called immediately after a new attendee registers.
    Converts their networking profile text into a vector and saves to Supabase.
    """
    profile_text = combine_profile_text(skills, interests, goals)
    embedding = get_embedding(profile_text)
    save_embedding(attendee_id, embedding)
    print(f"[Matchmaking] Embedding saved for attendee {attendee_id[:8]}...")
    return embedding


# ─────────────────────────────────────────────────────────────
#  LAYER 2: Similarity Search
# ─────────────────────────────────────────────────────────────

def get_top_matches(attendee_id: str, limit: int = 5) -> list[dict]:
    """
    Fetches the attendee's embedding from Supabase and runs cosine similarity
    against all other checked-in attendees via the match_attendees() RPC.
    Returns top-N matches sorted by similarity score.
    """
    attendee = get_attendee_by_id(attendee_id)
    if not attendee or not attendee.get("embedding"):
        print(f"[Matchmaking] No embedding found for {attendee_id}")
        return []

    matches = find_matches(
        query_embedding=attendee["embedding"],
        exclude_id=attendee_id,
        limit=limit,
    )
    return matches


# ─────────────────────────────────────────────────────────────
#  LAYER 3: Ice-Breaker Generation
# ─────────────────────────────────────────────────────────────

def generate_icebreaker(person_a: dict, person_b: dict) -> str:
    """
    Uses OpenRouter LLM to write a personalized ice-breaker message
    explaining WHY these two specific people should meet.
    """
    prompt = f"""
You are an AI matchmaker at a college tech event. Write a short, enthusiastic, 
personalized introduction message (max 3 sentences) explaining why these two students should meet.

Person A:
- Name: {person_a['name']}
- Skills: {person_a.get('skills', '')}
- Goals: {person_a.get('goals', '')}

Person B:
- Name: {person_b['name']}
- Skills: {person_b.get('skills', '')}
- Goals: {person_b.get('goals', '')}

Focus on their specific complementary skills or shared goals. Be specific and exciting.
Start with "🤝 You should meet" and end with their names.
"""
    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


def build_match_message(person_a: dict, person_b: dict, meeting_point: str = "the Networking Zone") -> str:
    """
    Builds the full Telegram message sent to each person in the matched pair.
    """
    icebreaker = generate_icebreaker(person_a, person_b)
    return (
        f"🎯 *AI Matchmaking Found You a Connection!*\n\n"
        f"{icebreaker}\n\n"
        f"📍 *Suggested meeting point:* {meeting_point}\n\n"
        f"What would you like to do?"
    )


# ─────────────────────────────────────────────────────────────
#  LAYER 3: Active Outreach Runner (called by Telegram bot)
# ─────────────────────────────────────────────────────────────

async def run_matchmaking_blast(bot, meeting_point: str = "the Networking Zone") -> int:
    """
    Admin triggers /run_matchmaking in the Telegram bot.
    This function:
    1. Gets all checked-in attendees
    2. For each, finds their best unmatched match
    3. Sends personalized ice-breaker DMs to both with Accept/Next buttons

    Returns the number of matches sent.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    attendees = get_checked_in_attendees()
    matched_pairs = set()
    sent_count = 0

    for person_a in attendees:
        if not person_a.get("telegram_id"):
            continue
        aid = person_a["id"]

        matches = get_top_matches(aid, limit=5)
        if not matches:
            continue

        # Find first match not already paired in this run
        for match in matches:
            pair = frozenset([aid, match["id"]])
            if pair in matched_pairs:
                continue
            matched_pairs.add(pair)

            person_b = match

            # Build message
            msg = build_match_message(person_a, person_b, meeting_point)

            # Accept/Next keyboard — callback_data encodes pair info
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Accept & Share Contact", callback_data=f"match_accept|{aid}|{person_b['id']}"),
                    InlineKeyboardButton("⏭ Next Match", callback_data=f"match_next|{aid}|{person_b['id']}"),
                ]
            ])

            # Send to Person A
            try:
                await bot.send_message(
                    chat_id=person_a["telegram_id"],
                    text=msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception as e:
                print(f"[Matchmaking] Failed to DM {person_a['name']}: {e}")

            # Send to Person B (mirror message)
            if person_b.get("telegram_id"):
                msg_b = build_match_message(person_b, person_a, meeting_point)
                keyboard_b = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Accept & Share Contact", callback_data=f"match_accept|{person_b['id']}|{aid}"),
                        InlineKeyboardButton("⏭ Next Match", callback_data=f"match_next|{person_b['id']}|{aid}"),
                    ]
                ])
                try:
                    await bot.send_message(
                        chat_id=person_b["telegram_id"],
                        text=msg_b,
                        parse_mode="Markdown",
                        reply_markup=keyboard_b,
                    )
                except Exception as e:
                    print(f"[Matchmaking] Failed to DM {person_b['name']}: {e}")

            # Record as pending match
            record_match_interaction(aid, person_b["id"], "pending")
            sent_count += 1
            break  # one active match per person per blast

    print(f"[Matchmaking] Sent {sent_count} match introductions.")
    return sent_count
