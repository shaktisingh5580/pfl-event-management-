"""
agents/concierge_agent.py
RAG-powered FAQ bot — answers attendee questions using event-specific documents
stored as pgvector embeddings in Supabase.
"""
from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, EVENT_NAME, OUTPUTS_DIR
from tools.embedding_tool import get_embedding
from tools.supabase_tool import _client as sb_client


_llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

# In-memory knowledge base (populated on first load)
_knowledge_chunks: list[dict] = []


def load_knowledge_base():
    """
    Loads the rulebook and event schedule into the in-memory knowledge base.
    In production, this would be pre-embedded and stored in Supabase.
    """
    global _knowledge_chunks
    if _knowledge_chunks:
        return  # Already loaded

    chunks = []

    # Load rulebook markdown
    rulebook_path = OUTPUTS_DIR / "rulebooks" / "rulebook.md"
    if rulebook_path.exists():
        text = rulebook_path.read_text(encoding="utf-8")
        # Split into paragraphs
        for para in text.split("\n\n"):
            if para.strip():
                chunks.append({"source": "rulebook", "text": para.strip()})

    # Load schedule JSON
    import json
    schedule_path = OUTPUTS_DIR / "schedule.json"
    if schedule_path.exists():
        data = json.loads(schedule_path.read_text())
        # The schedule.json created by the architect has it nested as data['plan']['plan']
        plan = data.get("plan", {}).get("plan", {})
        if not plan:
            plan = data.get("plan", {})

        for slot in plan.get("schedule", []):
            chunks.append({
                "source": "schedule",
                "text": f"At {slot['time']}, {slot['activity']} happens at {slot['location']}. {slot.get('notes', '')}",
            })
        for act in plan.get("activities", []):
            chunks.append({
                "source": "activities",
                "text": f"{act['name']}: {act['description']}. Max participants: {act['max_participants']}. Prizes: {act['prizes']}",
            })

    # Add dynamic FAQ from the plan data (rules, resources, event info)
    static_faq = []

    # Pull venue/date/event context
    if schedule_path.exists():
        try:
            event_venue = plan.get("venue", "the event venue")
            event_date = plan.get("date", "")
            event_desc = plan.get("description", "")
            static_faq.append({"source": "faq", "text": f"The event '{plan.get('event_name', EVENT_NAME)}' is on {event_date} at {event_venue}. {event_desc}"})

            # Rules from the plan
            for rule in plan.get("rules", []):
                static_faq.append({"source": "rules", "text": rule})

            # Resources (rooms, equipment, etc.)
            resources = plan.get("resources", {})
            if resources.get("rooms"):
                rooms_text = ", ".join(resources["rooms"])
                static_faq.append({"source": "faq", "text": f"Available rooms/halls for the event: {rooms_text}"})
            if resources.get("equipment"):
                equip_text = ", ".join(resources["equipment"])
                static_faq.append({"source": "faq", "text": f"Equipment available: {equip_text}"})
            if resources.get("budget_estimate_inr"):
                static_faq.append({"source": "faq", "text": f"Estimated budget for the event: ₹{resources['budget_estimate_inr']}"})

            # Judging criteria
            for criterion in plan.get("judging_criteria", []):
                static_faq.append({"source": "faq", "text": f"Judging criterion: {criterion}"})
        except Exception:
            pass

    # Generic fallback FAQ entries (always included)
    static_faq.extend([
        {"source": "faq", "text": "Restrooms are located on each floor near the staircase."},
        {"source": "faq", "text": "Medical aid is available at the First Aid room near the main entrance."},
        {"source": "faq", "text": f"If you face any issues, visit the Help Desk near the reception or message this bot."},
        {"source": "faq", "text": "Photography is allowed everywhere except during judging sessions."},
    ])
    chunks.extend(static_faq)

    _knowledge_chunks = chunks
    print(f"[Concierge] Loaded {len(chunks)} knowledge chunks.")


def _find_relevant_chunks(query: str, top_k: int = 3) -> list[str]:
    """Simple semantic search using cosine similarity over in-memory chunks."""
    if not _knowledge_chunks:
        load_knowledge_base()

    import numpy as np
    query_emb = get_embedding(query)

    # Score each chunk
    scored = []
    for chunk in _knowledge_chunks:
        if "_emb" not in chunk:
            chunk["_emb"] = get_embedding(chunk["text"])
        a, b = query_emb, chunk["_emb"]
        cos_sim = sum(x * y for x, y in zip(a, b)) / (
            (sum(x**2 for x in a)**0.5) * (sum(x**2 for x in b)**0.5) + 1e-9
        )
        scored.append((cos_sim, chunk["text"]))

    scored.sort(reverse=True)
    return [text for _, text in scored[:top_k]]


async def answer_question(question: str) -> str:
    """
    Answers an attendee question using RAG:
    1. Finds relevant chunks from the knowledge base
    2. Uses OpenRouter LLM to generate a helpful, concise answer
    """
    load_knowledge_base()
    relevant = _find_relevant_chunks(question)
    context = "\n".join(f"- {c}" for c in relevant)

    prompt = f"""You are a helpful assistant for {EVENT_NAME}. 
Answer the attendee's question using ONLY the provided context.
If the answer isn't in the context, say "Please check with event staff."
Be friendly, brief (max 2 sentences), and use emojis sparingly.

Context:
{context}

Question: {question}
Answer:"""

    response = _llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()
