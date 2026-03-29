"""
tools/embedding_tool.py
Generates text embeddings via OpenRouter (text-embedding-3-small).
Used for: semantic matchmaking, RAG concierge, pgvector storage.
"""
from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_EMBED_MODEL


_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def get_embedding(text: str, model: str = OPENROUTER_EMBED_MODEL) -> list[float]:
    """
    Convert any text into a 1536-dimensional vector.
    
    Args:
        text: The text to embed (skills + interests + goals combined for matchmaking)
        model: Embedding model identifier on OpenRouter
    
    Returns:
        List of 1536 floats representing the semantic meaning of the text.
    """
    text = text.replace("\n", " ").strip()
    response = _client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def combine_profile_text(skills: str, interests: str, goals: str) -> str:
    """
    Combines the three networking fields into a single coherent profile string
    for more accurate embedding. Weighting: goals matter most.
    """
    return (
        f"Skills and expertise: {skills}. "
        f"Areas of interest: {interests}. "
        f"What I want to achieve: {goals}."
    )
