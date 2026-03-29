# AutoEvent Backend & Bot Architecture

Welcome to the backend for **AutoEvent**, an elite AI-powered event management system. This repository contains the FastAPI server, the Telegram Bot, and the complete swarm of LangChain/OpenAI agents that power the event orchestration.

## Features Included
1. **AI Architect**: Chat-based UI to design the entire event schedule.
2. **Web Deployer**: Automatically generates and pushes static event landing pages.
3. **Telegram Bot**: Core interactive interface for attendees (check-in, concierge, matchmaking).
4. **Dynamic Check-in Pipeline**: Creates personalized welcome PDFs with schedule + seat mapping and automatically triggers matchmaking vectors upon check-in.
5. **During-Event API**: Exposes RAG concierge, social wall, check-ins, complaints, and matchmaking to any frontend dashboard.

---

## 🚀 Setup Instructions

### 1. Database Setup (Supabase)
We use Supabase for PostgreSQL, Storage, and Auth.
1. Create a new project at [Supabase](https://supabase.com).
2. Go to the **SQL Editor**, paste the contents of `supabase_fresh.sql` located in this repository, and run it. This will create all the necessary schemas, tables, and RPC functions.

### 2. Environment Variables (.env)
Create a `.env` file in the root of the project. **Never commit this file.**
Here is the template of what you need to fill in:

```env
# ── Groq / OpenRouter (LLM) ──────────────────────────────
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=mistralai/mistral-small-3.1-24b-instruct:free
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small

# ── Supabase ───────────────────────────────────────────────
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# ── Telegram Bot ───────────────────────────────────────────
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id
TELEGRAM_GROUP_CHAT_ID=your_group_chat_id

# ── GitHub (For website deploys) ───────────────────────────
GITHUB_TOKEN=your_github_token
GITHUB_USERNAME=your_github_username

# ── Vercel (For website deploys) ───────────────────────────
VERCEL_TOKEN=your_vercel_token
VERCEL_TEAM_ID=your_team_id_if_applicable

# ── Cloudinary (For Social Wall images) ────────────────────
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# ── Event Configuration (Changes per event) ────────────────
EVENT_NAME=Autoevent 2026
EVENT_DATE=2026-03-30
EVENT_VENUE=Vesu, Surat
EVENT_HASHTAG=#AutoEvent2026
EVENT_WEBSITE_URL=https://your-website.vercel.app
```

### 3. Installation
Ensure you have Python 3.10+ installed.

```bash
# It is recommended to use a virtual environment
pip install -r requirements.txt
```
*(If `requirements.txt` is missing, you will need: `fastapi uvicorn python-telesign python-telegram-bot[job-queue] supabase openai httpx pydantic pillow qrcode reportlab jinja2 cloudinary`)*

### 4. Running the System
You need to run both the API server and the Telegram Bot concurrently.

**Terminal 1 (The Dashboard API):**
```bash
python -m api.server
# Runs on http://0.0.0.0:8000
```

**Terminal 2 (The Telegram Bot):**
```bash
python run_bot.py
```

---

## 🎨 Frontend Details

If you'd like to build the Frontend Dashboard, view the `FRONTEND_PROMPT.md` file included in this repository. It contains the exact prompt required for an AI generation tool (like v0.dev or Claude) to fully generate the Next.js React Dashboard bridging all the endpoints in `api/server.py`.
