"""
config.py — Centralized configuration loader for the AI Event Management System.
All agents import from here; never import os.getenv() directly in agent files.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM — auto-selects Groq (preferred) or OpenRouter ──────
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")

# Unified LLM config used by all agents
if GROQ_API_KEY:
    LLM_API_KEY  = GROQ_API_KEY
    LLM_BASE_URL = "https://api.groq.com/openai/v1"
    LLM_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
else:
    LLM_API_KEY  = OPENROUTER_API_KEY
    LLM_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_MODEL    = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-small-3.1-24b-instruct:free")

# Embedding — use OpenRouter (Groq doesn't have embedding models)
OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small")

# Legacy aliases so existing imports don't break
OPENROUTER_BASE_URL = LLM_BASE_URL
OPENROUTER_MODEL    = LLM_MODEL

# ── Supabase ────────────────────────────────────────────────
SUPABASE_URL              = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY         = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID  = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))
TELEGRAM_GROUP_CHAT_ID  = int(os.getenv("TELEGRAM_GROUP_CHAT_ID", "0"))

# ── GitHub ──────────────────────────────────────────────────
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

# ── Vercel ──────────────────────────────────────────────────
VERCEL_TOKEN   = os.getenv("VERCEL_TOKEN", "")
VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID", "")

# ── Cloudinary ──────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME  = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY     = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET  = os.getenv("CLOUDINARY_API_SECRET", "")

# ── Google ───────────────────────────────────────────────────
GOOGLE_MAPS_API_KEY    = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

# ── Buffer ───────────────────────────────────────────────────
BUFFER_ACCESS_TOKEN          = os.getenv("BUFFER_ACCESS_TOKEN", "")
BUFFER_INSTAGRAM_PROFILE_ID  = os.getenv("BUFFER_INSTAGRAM_PROFILE_ID", "")
BUFFER_LINKEDIN_PROFILE_ID   = os.getenv("BUFFER_LINKEDIN_PROFILE_ID", "")

# ── Event Identity ───────────────────────────────────────────
EVENT_NAME        = os.getenv("EVENT_NAME", "TechFest 2026")
EVENT_DATE        = os.getenv("EVENT_DATE", "2026-03-15")
EVENT_VENUE       = os.getenv("EVENT_VENUE", "SVIT College, Vasad, Surat")
EVENT_HASHTAG     = os.getenv("EVENT_HASHTAG", "#TechFest2026")
EVENT_WEBSITE_URL = os.getenv("EVENT_WEBSITE_URL", "")

# ── Paths ────────────────────────────────────────────────────
import pathlib
BASE_DIR    = pathlib.Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"
ASSETS_DIR  = BASE_DIR / "assets"

OUTPUTS_DIR.mkdir(exist_ok=True)
(OUTPUTS_DIR / "posters").mkdir(exist_ok=True)
(OUTPUTS_DIR / "certificates").mkdir(exist_ok=True)
(OUTPUTS_DIR / "reports").mkdir(exist_ok=True)
(OUTPUTS_DIR / "rulebooks").mkdir(exist_ok=True)
(OUTPUTS_DIR / "tickets").mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)
