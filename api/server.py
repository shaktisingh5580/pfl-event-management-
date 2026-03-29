import os
import json
import subprocess
import sys
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import config

# Import existing agents
from agents.architect_agent import generate_event_plan, architect_chat, load_templates, get_template_by_id
from agents.web_deployer_agent import generate_site_files, run_web_deployer, redeploy_website
from agents.generative_ui_agent import generate_code_update
from agents.branding_agent import generate_poster, apply_local_overlay, run_branding
from tools.pdf_ingestion_tool import ingest_pdf_to_knowledge_base

app = FastAPI(title="PFL Event Management API", version="2.0.0")

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global State ──────────────────────────────────────────────────────────────
bot_process = None
_architect_sessions: dict[str, dict] = {}  # session_id -> {history, template_id}

# Pipeline status tracks what has been auto-triggered after plan finalization
_pipeline_status: dict[str, str] = {
    "plan": "not_started",
    "poster": "not_started",
    "website": "not_started",
    "sponsors": "not_started",
    "scheduler": "not_started",
}

def _run_pipeline_step(step_name: str, func, *args, **kwargs):
    """Run a pipeline step and update status."""
    try:
        _pipeline_status[step_name] = "running..."
        result = func(*args, **kwargs)
        _pipeline_status[step_name] = "done"
        return result
    except Exception as e:
        _pipeline_status[step_name] = f"error: {str(e)[:100]}"
        print(f"[Pipeline] {step_name} failed: {e}")
        return None

def _auto_distribute_plan(plan: dict):
    """Background task: distribute finalized plan to poster, website, sponsors."""
    import time
    
    # Normalize plan in case it came in as double-nested (e.g. {"plan": {"plan": {...}}})
    while "plan" in plan and isinstance(plan["plan"], dict) and "event_name" not in plan:
        plan = plan["plan"]
        
    _pipeline_status["plan"] = "ready"

    # Step 0: Save plan to Supabase events table
    try:
        from tools.supabase_tool import _client as _sb
        event_row = {
            "name": plan.get("event_name", config.EVENT_NAME),
            "event_type": plan.get("event_type", ""),
            "date": plan.get("date", config.EVENT_DATE),
            "venue": plan.get("venue", config.EVENT_VENUE),
            "theme": plan.get("theme", ""),
            "description": plan.get("description", ""),
            "plan": plan,
        }
        _sb().table("events").upsert(event_row, on_conflict="name").execute()
        print(f"[Pipeline] Event plan saved to Supabase events table")
    except Exception as e:
        print(f"[Pipeline] Could not save plan to events table: {e}")

    # Step 1: Generate poster
    try:
        _pipeline_status["poster"] = "generating..."
        poster_path = run_branding(plan, website_url=config.EVENT_WEBSITE_URL)
        _pipeline_status["poster"] = f"done → {poster_path}" if poster_path else "done"
    except Exception as e:
        _pipeline_status["poster"] = f"error: {str(e)[:80]}"
        print(f"[Pipeline] Poster failed: {e}")

    # Step 2: Deploy website
    try:
        _pipeline_status["website"] = "deploying..."
        url = run_web_deployer(plan)
        _pipeline_status["website"] = f"live → {url}" if url else "done"
    except Exception as e:
        _pipeline_status["website"] = f"error: {str(e)[:80]}"
        print(f"[Pipeline] Website failed: {e}")

    # Step 3: Match sponsors
    try:
        _pipeline_status["sponsors"] = "matching..."
        from agents.sponsor_agent import get_sponsors_for_event
        event_type = plan.get("event_type", "techfest").lower().replace(" ", "_")
        sponsors = get_sponsors_for_event(event_type)
        _pipeline_status["sponsors"] = f"done → {len(sponsors)} found"
    except Exception as e:
        _pipeline_status["sponsors"] = f"error: {str(e)[:80]}"
        print(f"[Pipeline] Sponsors failed: {e}")



# ── Pydantic Models ───────────────────────────────────────────────────────────

class ArchitectChatRequest(BaseModel):
    message: str
    event_id: str = None
    session_id: str = "default"
    template_id: str = None

class DeployWebsiteRequest(BaseModel):
    plan: dict
    event_id: str = None

class GenerativeUIRequest(BaseModel):
    messages_history: list
    current_code: str
    event_id: str = None

class ParticipantLoginRequest(BaseModel):
    email: str
    password: str
    event_id: str

class ParticipantChatRequest(BaseModel):
    message: str
    attendee_id: str
    telegram_id: int = None
    event_id: str = None

class UploadWallPhotoRequest(BaseModel):
    image_base64: str
    attendee_id: str
    sender_name: str
    event_id: str = None

class SponsorEmailRequest(BaseModel):
    event_type_id: str
    selected_companies: list[str] = []
    from_email: str
    smtp_password: str
    organizer_name: str = "The Organizing Team"
    organizer_phone: str = ""

class SponsorPreviewRequest(BaseModel):
    sponsor_company: str
    event_type_id: str
    organizer_name: str = "The Organizing Team"
    organizer_email: str = ""
    organizer_phone: str = ""

class SchedulerStartRequest(BaseModel):
    skip_slots: list[str] = []
    wellness_interval_mins: int = 90

class CustomBlastRequest(BaseModel):
    message: str
    at_time: str
    job_id: str = "custom_blast"
    target: str = "both"

class CertificateDeliveryRequest(BaseModel):
    rank_mapping: dict = {}

class GeneratePosterRequest(BaseModel):
    website_url: str = ""

class RegisterAttendeeRequest(BaseModel):
    name: str
    email: str
    password: str = ""
    phone: str = ""
    college: str = ""
    department: str = ""
    year_of_study: str = ""
    telegram_username: str = ""
    skills: str = ""
    interests: str = ""
    goals: str = ""
    team_preference: str = "solo"
    event_id: str = ""
    dynamic_fields: dict = {}


# ── Basic Health ──────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "ok", "service": "PFL Event Management", "event_name": config.EVENT_NAME}


# ═══════════════════════════════════════════════════════════════════════════════
#  DYNAMIC REGISTRATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# Standard fields that always exist in the attendees table
_STANDARD_FIELDS = [
    {"field_name": "name", "display_label": "Full Name", "field_type": "text", "required": True, "options": []},
    {"field_name": "email", "display_label": "Email Address", "field_type": "email", "required": True, "options": []},
    {"field_name": "password", "display_label": "Create Password", "field_type": "password", "required": True, "options": []},
    {"field_name": "phone", "display_label": "Phone Number", "field_type": "tel", "required": False, "options": []},
    {"field_name": "college", "display_label": "College / Organization", "field_type": "text", "required": False, "options": []},
    {"field_name": "department", "display_label": "Department", "field_type": "select", "required": False, "options": ["CE", "IT", "EC", "EE", "ME", "Other"]},
    {"field_name": "year_of_study", "display_label": "Year of Study", "field_type": "select", "required": False, "options": ["FY", "SY", "TY", "LY", "PG"]},
    {"field_name": "telegram_username", "display_label": "Telegram Username", "field_type": "text", "required": False, "options": []},
    {"field_name": "skills", "display_label": "Skills (comma separated)", "field_type": "text", "required": False, "options": []},
    {"field_name": "interests", "display_label": "Interests", "field_type": "textarea", "required": False, "options": []},
    {"field_name": "goals", "display_label": "Goals for this event", "field_type": "textarea", "required": False, "options": []},
    {"field_name": "team_preference", "display_label": "Team Preference", "field_type": "radio", "required": False, "options": ["solo", "have_team", "looking_for_team"]},
]


@app.get("/api/registration-fields")
def get_registration_fields(event_id: str = ""):
    """
    Returns the full registration form config: standard fields + custom fields.
    Any frontend can use this to dynamically render the registration form.
    """
    plan_path = config.OUTPUTS_DIR / "schedule.json"
    custom_fields = []
    if plan_path.exists():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            raw_custom = plan.get("custom_registration_fields", [])
            # Normalize: ensure each custom field has all required keys
            for f in raw_custom:
                custom_fields.append({
                    "field_name": f.get("field_name", f.get("display_label", "custom").lower().replace(" ", "_")),
                    "display_label": f.get("display_label", f.get("field_name", "Custom Field")),
                    "field_type": f.get("field_type", "text"),
                    "required": f.get("required", False),
                    "options": f.get("options", []),
                    "is_dynamic": True,  # marker so frontend knows this goes into dynamic_fields
                })
        except Exception as e:
            print(f"[API] Error loading custom fields: {e}")

    return {
        "standard_fields": _STANDARD_FIELDS,
        "custom_fields": custom_fields,
        "event_name": config.EVENT_NAME,
    }


@app.post("/api/register")
def register_attendee_endpoint(req: RegisterAttendeeRequest):
    """
    Register a new attendee. Standard fields go to table columns,
    custom fields go into the dynamic_fields JSONB column.
    Uses the register_attendee RPC for proper password hashing.
    """
    try:
        from tools.supabase_tool import _client as _sb

        # Call the register_attendee RPC which handles password hashing
        rpc_params = {
            "p_name": req.name,
            "p_email": req.email,
            "p_phone": req.phone,
            "p_password": req.password,
            "p_event_id": req.event_id,
            "p_telegram_username": req.telegram_username.lstrip("@") if req.telegram_username else "",
            "p_dynamic_fields": json.dumps(req.dynamic_fields) if req.dynamic_fields else "{}",
        }
        response = _sb().rpc("register_attendee", rpc_params).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=500, detail="Registration failed — no row returned")

        attendee = response.data[0]

        # Update additional standard fields not covered by the RPC
        extra_fields = {}
        if req.college:
            extra_fields["college"] = req.college
        if req.department:
            extra_fields["department"] = req.department
        if req.year_of_study:
            extra_fields["year_of_study"] = req.year_of_study
        if req.skills:
            extra_fields["skills"] = req.skills
        if req.interests:
            extra_fields["interests"] = req.interests
        if req.goals:
            extra_fields["goals"] = req.goals
        if req.team_preference:
            extra_fields["team_preference"] = req.team_preference

        if extra_fields:
            _sb().table("attendees").update(extra_fields).eq("id", attendee["id"]).execute()

        return {
            "status": "success",
            "attendee_id": attendee["id"],
            "name": attendee["name"],
            "message": "Registration successful!",
        }

    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e)
        if "23505" in err_str or "duplicate" in err_str.lower():
            raise HTTPException(status_code=409, detail="An account with this email already exists. Please log in.")
        raise HTTPException(status_code=500, detail=f"Registration failed: {err_str}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PRE-EVENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Templates ─────────────────────────────────────────────────────────────────

@app.get("/api/templates")
def get_templates():
    """Return all available event templates."""
    return {"templates": load_templates()}

@app.get("/api/templates/{template_id}")
def get_template(template_id: str):
    """Return a single template by ID."""
    t = get_template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return t


# ── AI Architect Chat (Stateless, history managed per session) ─────────────

@app.post("/api/architect/chat")
def architect_chat_endpoint(req: ArchitectChatRequest, background_tasks: BackgroundTasks):
    """
    Stateless API chat with the AI Architect.
    Maintains history per session_id in-memory.
    """
    session = _architect_sessions.get(req.session_id, {"history": [], "template_id": req.template_id})
    if req.template_id:
        session["template_id"] = req.template_id

    result = architect_chat(
        message=req.message,
        history=session["history"],
        template_id=session.get("template_id"),
    )

    _architect_sessions[req.session_id] = {
        "history": result["history"],
        "template_id": session.get("template_id"),
    }

    if result["finalized"] and result.get("plan"):
        # Store plan in outputs/schedule.json (already done inside architect_chat)
        _architect_sessions.pop(req.session_id, None)  # clear session
        # Auto-distribute plan to all agents in background
        background_tasks.add_task(_auto_distribute_plan, result["plan"])

    return {
        "reply": result["reply"],
        "finalized": result["finalized"],
        "plan": result.get("plan"),
        "session_id": req.session_id,
        "pipeline_started": result["finalized"] and result.get("plan") is not None,
    }

@app.delete("/api/architect/session/{session_id}")
def clear_architect_session(session_id: str):
    """Clear an architect chat session (start fresh)."""
    _architect_sessions.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


# ── Plan Viewer & Pipeline Status ─────────────────────────────────────────────

@app.get("/api/plan")
def get_saved_plan():
    """View the current saved event plan."""
    plan_path = config.OUTPUTS_DIR / "schedule.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="No plan generated yet. Chat with AI Architect first.")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    return {"plan": plan}

@app.put("/api/plan")
def update_saved_plan(plan: dict):
    """Edit the saved plan (e.g. change schedule, add activities)."""
    plan_path = config.OUTPUTS_DIR / "schedule.json"
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return {"status": "updated", "message": "Plan saved. Use individual endpoints to re-run specific agents."}

@app.get("/api/pipeline/status")
def pipeline_status():
    """Check status of all auto-triggered pipeline steps."""
    return {"pipeline": _pipeline_status}

@app.post("/api/pipeline/rerun/{step}")
def rerun_pipeline_step(step: str, background_tasks: BackgroundTasks):
    """
    Re-run a specific pipeline step: poster, website, or sponsors.
    Useful when user edits the plan or wants to regenerate something.
    """
    plan_path = config.OUTPUTS_DIR / "schedule.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="No plan found")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    # Normalize plan in case it came in as double-nested
    while "plan" in plan and isinstance(plan["plan"], dict) and "event_name" not in plan:
        plan = plan["plan"]

    if step == "poster":
        _pipeline_status["poster"] = "queued..."
        background_tasks.add_task(
            _run_pipeline_step, "poster", run_branding, plan, config.EVENT_WEBSITE_URL
        )
    elif step == "website":
        _pipeline_status["website"] = "queued..."
        background_tasks.add_task(
            _run_pipeline_step, "website", run_web_deployer, plan
        )
    elif step == "sponsors":
        _pipeline_status["sponsors"] = "queued..."
        from agents.sponsor_agent import get_sponsors_for_event
        event_type = plan.get("event_type", "techfest").lower().replace(" ", "_")
        background_tasks.add_task(
            _run_pipeline_step, "sponsors", get_sponsors_for_event, event_type
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step}. Use: poster, website, sponsors")

    return {"status": "queued", "step": step}


# ── Branding / Poster ─────────────────────────────────────────────────────────

@app.post("/api/branding/generate")
def generate_poster_endpoint(req: GeneratePosterRequest, background_tasks: BackgroundTasks):
    """
    Generate event poster (Pollinations.AI → Pillow overlay + QR code).
    Returns the path to the generated PNG.
    """
    schedule_path = config.OUTPUTS_DIR / "schedule.json"
    if not schedule_path.exists():
        raise HTTPException(status_code=400, detail="Run AI Architect first to generate event plan")

    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    try:
        branded_path = run_branding(plan, website_url=req.website_url or config.EVENT_WEBSITE_URL)
        return {
            "status": "success",
            "poster_path": str(branded_path),
            "filename": branded_path.name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/branding/poster")
def download_poster():
    """Download the generated poster PNG."""
    poster_path = config.OUTPUTS_DIR / "posters" / "poster_branded.png"
    if not poster_path.exists():
        raise HTTPException(status_code=404, detail="Poster not generated yet")
    return FileResponse(str(poster_path), media_type="image/png", filename="event_poster.png")


# ── Sponsors ─────────────────────────────────────────────────────────────────

@app.get("/api/sponsors")
def list_sponsors(event_type_id: str = "techfest", limit: int = 20):
    """Return list of relevant sponsors for an event type."""
    from agents.sponsor_agent import get_sponsors_for_event, get_all_tiers
    return {
        "sponsors": get_sponsors_for_event(event_type_id, limit),
        "tiers": get_all_tiers(),
    }

@app.get("/api/sponsors/call-list")
def get_call_list(event_type_id: str = "techfest"):
    """Return sponsors with phone numbers for manual outreach."""
    from agents.sponsor_agent import get_call_list
    return {"call_list": get_call_list(event_type_id)}

@app.post("/api/sponsors/preview-email")
def preview_sponsor_email(req: SponsorPreviewRequest):
    """Generate a preview of the sponsorship email for a specific company."""
    from agents.sponsor_agent import preview_sponsor_email as _preview

    schedule_path = config.OUTPUTS_DIR / "schedule.json"
    plan = json.loads(schedule_path.read_text(encoding="utf-8")) if schedule_path.exists() else {}

    result = _preview(
        sponsor_company=req.sponsor_company,
        event_type_id=req.event_type_id,
        event_plan=plan,
        organizer_name=req.organizer_name,
        organizer_email=req.organizer_email,
        organizer_phone=req.organizer_phone,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.post("/api/sponsors/send-emails")
def send_sponsor_emails(req: SponsorEmailRequest):
    """Blast sponsorship emails to selected (or all relevant) sponsors."""
    from agents.sponsor_agent import blast_sponsor_emails

    schedule_path = config.OUTPUTS_DIR / "schedule.json"
    plan = json.loads(schedule_path.read_text(encoding="utf-8")) if schedule_path.exists() else {}

    results = blast_sponsor_emails(
        sponsor_ids_or_all=req.selected_companies or None,
        event_plan=plan,
        event_type_id=req.event_type_id,
        organizer_name=req.organizer_name,
        from_email=req.from_email,
        smtp_password=req.smtp_password,
        organizer_phone=req.organizer_phone,
    )
    return results


# ── Website Deployer ──────────────────────────────────────────────────────────

@app.post("/api/deploy")
def deploy_website(req: DeployWebsiteRequest):
    """Trigger Website Generation and Deployment to Vercel."""
    try:
        url = run_web_deployer(req.plan)
        return {"status": "success", "url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/deploy/redeploy")
def redeploy():
    """Push local edits to Vercel without regenerating via LLM."""
    try:
        url = redeploy_website()
        return {"status": "success", "url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/website/generate")
def generative_ui_update(req: GenerativeUIRequest):
    """v0-style continuous website editing via AI chat."""
    try:
        updated_html = generate_code_update(req.messages_history, req.current_code)
        return {"html": updated_html}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge-base/upload")
async def upload_pdf(file: UploadFile = File(...), description: str = Form("")):
    """Ingest a PDF into the Vector Knowledge Base."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    os.makedirs(config.OUTPUTS_DIR / "uploads", exist_ok=True)
    temp_path = config.OUTPUTS_DIR / "uploads" / file.filename
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
    success = ingest_pdf_to_knowledge_base(str(temp_path), description)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to ingest PDF")
    return {"status": "success", "filename": file.filename}


# ═══════════════════════════════════════════════════════════════════════════════
#  DURING-EVENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Scheduler ─────────────────────────────────────────────────────────────────

@app.get("/api/scheduler/status")
def scheduler_status():
    """Return current scheduler status and job list."""
    from agents.scheduler_agent import get_status
    return get_status()

@app.post("/api/scheduler/start")
def start_scheduler(req: SchedulerStartRequest):
    """Start the announcement scheduler."""
    from agents.scheduler_agent import start_scheduler as _start
    result = _start(
        skip_slots=req.skip_slots,
        wellness_interval_mins=req.wellness_interval_mins,
    )
    return result

@app.post("/api/scheduler/stop")
def stop_scheduler():
    """Stop the announcement scheduler."""
    from agents.scheduler_agent import stop_scheduler as _stop
    return _stop()

@app.post("/api/scheduler/blast")
def schedule_custom_blast(req: CustomBlastRequest):
    """Schedule a one-off custom Telegram blast at a specific time."""
    from agents.scheduler_agent import schedule_custom_blast as _blast
    success = _blast(
        message=req.message,
        at_time=req.at_time,
        job_id=req.job_id,
        target=req.target,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Scheduler not running or invalid time format")
    return {"status": "scheduled", "at_time": req.at_time}


# ── Complaints ────────────────────────────────────────────────────────────────

@app.get("/api/complaints")
def list_complaints(status: str = None, severity: str = None, limit: int = 50):
    """List complaints with optional filters."""
    try:
        from tools.supabase_tool import _client as _sb
        query = _sb().table("complaints").select("*").order("created_at", desc=True).limit(limit)
        if status:
            query = query.eq("status", status)
        if severity:
            query = query.eq("severity", severity)
        result = query.execute()
        return {"complaints": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/complaints/{complaint_id}/resolve")
def resolve_complaint(complaint_id: str, resolved_by: str = "admin"):
    """Mark a complaint as resolved."""
    try:
        from tools.supabase_tool import _client as _sb
        _sb().table("complaints").update({
            "status": "resolved",
            "resolved_by": resolved_by,
        }).eq("id", complaint_id).execute()
        return {"status": "resolved", "id": complaint_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feedback ──────────────────────────────────────────────────────────────────

@app.get("/api/feedback")
def list_feedback(limit: int = 50):
    """List all feedback submissions."""
    try:
        from tools.supabase_tool import _client as _sb
        result = _sb().table("feedback").select("*").order("created_at", desc=True).limit(limit).execute()
        return {"feedback": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Concierge (RAG Q&A) ──────────────────────────────────────────────────────

@app.post("/api/concierge/ask")
async def concierge_ask(question: str):
    """Ask the RAG concierge a question about the event."""
    try:
        from agents.concierge_agent import answer_question
        answer = await answer_question(question)
        return {"question": question, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Wall Photos ───────────────────────────────────────────────────────────────

@app.get("/api/wall-photos")
def list_wall_photos(status: str = "approved", limit: int = 50):
    """List social wall photos."""
    try:
        from tools.supabase_tool import _client as _sb
        query = _sb().table("wall_photos").select("*").order("created_at", desc=True).limit(limit)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return {"photos": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Checked-In Attendees ─────────────────────────────────────────────────────

@app.get("/api/attendees/checked-in")
def list_checked_in_attendees():
    """List all checked-in attendees with their dynamic_fields."""
    try:
        from tools.supabase_tool import _client as _sb
        result = _sb().table("attendees").select("*").eq("checked_in", True).execute()
        return {"attendees": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Matchmaking Trigger ──────────────────────────────────────────────────────

@app.post("/api/matchmaking/run")
async def run_matchmaking_api(meeting_point: str = "the Networking Zone"):
    """Trigger AI matchmaking blast (requires bot to be running for DMs)."""
    try:
        from agents.matchmaking_agent import get_top_matches
        from tools.supabase_tool import get_checked_in_attendees
        attendees = get_checked_in_attendees()
        all_matches = []
        for person in attendees:
            if not person.get("id"):
                continue
            matches = get_top_matches(person["id"], limit=3)
            if matches:
                all_matches.append({
                    "person": person.get("name", ""),
                    "matches": [{"name": m.get("name", ""), "score": m.get("similarity", 0)} for m in matches[:3]],
                })
        return {
            "status": "matches_computed",
            "meeting_point": meeting_point,
            "attendees_processed": len(attendees),
            "matches": all_matches[:20],
            "note": "To send DM introductions, trigger /run_matchmaking from the Telegram bot.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Bot Management ────────────────────────────────────────────────────────────

def get_bot_status():
    global bot_process
    if bot_process is None:
        return {"status": "stopped"}
    if bot_process.poll() is not None:
        bot_process = None
        return {"status": "stopped"}
    return {"status": "running"}

@app.get("/api/bot/status")
def bot_status():
    return get_bot_status()

@app.post("/api/bot/start")
def start_bot():
    global bot_process
    if bot_process is not None and bot_process.poll() is None:
        return {"status": "already_running"}
    try:
        bot_process = subprocess.Popen(
            [sys.executable, "run_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
        )
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start bot: {str(e)}")

@app.post("/api/bot/stop")
def stop_bot():
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        bot_process = None
        return {"status": "already_stopped"}
    try:
        bot_process.terminate()
        bot_process = None
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop bot: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
#  POST-EVENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Certificate Auto-Delivery ─────────────────────────────────────────────────

@app.post("/api/certificates/generate")
def generate_certificates(req: CertificateDeliveryRequest):
    """Generate certificates for all checked-in attendees (saves to disk only)."""
    from agents.certificate_agent import run_all_certificates
    try:
        paths = run_all_certificates(rank_mapping=req.rank_mapping or None)
        return {"status": "success", "certificates_generated": len(paths)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/certificates/send-all")
async def send_all_certificates(req: CertificateDeliveryRequest, background_tasks: BackgroundTasks):
    """
    Generate + send certificates to all attendees via Telegram DM.
    Runs as a background task — returns immediately with job info.
    """
    from agents.certificate_agent import send_certificates_via_telegram

    # Note: We can't pass the bot directly here since it runs as a subprocess.
    # This endpoint triggers the delivery; the bot process handles the actual sending
    # by reading a delivery_queue table in Supabase.
    # For now, we generate them and return paths; delivery is triggered from bot.
    from agents.certificate_agent import run_all_certificates
    try:
        paths = run_all_certificates(rank_mapping=req.rank_mapping or None)
        return {
            "status": "certificates_generated",
            "count": len(paths),
            "message": "Certificates generated. Start the bot and use /send_certs to deliver via Telegram.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/certificates/send-feedback")
async def send_feedback_form(background_tasks: BackgroundTasks):
    """
    Broadcast post-event feedback poll to all attendees via Telegram.
    Triggers via bot. Returns status.
    """
    return {
        "status": "trigger_via_bot",
        "message": "Start the bot and use /send_feedback to deliver the feedback poll to all attendees.",
    }


# ── ROI Report ────────────────────────────────────────────────────────────────

@app.post("/api/reports/roi")
def generate_roi_report():
    """Generate and return the post-event ROI report PDF."""
    from agents.report_agent import generate_roi_report as _gen
    schedule_path = config.OUTPUTS_DIR / "schedule.json"
    plan = json.loads(schedule_path.read_text(encoding="utf-8")) if schedule_path.exists() else {}
    try:
        pdf_path = _gen(event_plan=plan)
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename="roi_report.pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  PARTICIPANT ENDPOINTS (unchanged from v1)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/participant/login")
def participant_login(req: ParticipantLoginRequest):
    try:
        from tools.supabase_tool import _client
        rpc_params = {"p_email": req.email, "p_password": req.password, "p_event_id": req.event_id}
        response = _client().rpc("authenticate_attendee", rpc_params).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        attendee = response.data[0]
        return {"status": "success", "user": attendee}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/participant/chat")
async def participant_chat(req: ParticipantChatRequest):
    from bot.telegram_bot import _classify_intent
    from agents.concierge_agent import answer_question
    from agents.complaint_agent import categorize_and_log_complaint
    from tools.supabase_tool import save_feedback

    intent, confidence = await _classify_intent(req.message)
    if intent == "complaint" and confidence >= 0.70:
        row = await categorize_and_log_complaint(
            text=req.message, telegram_id=req.telegram_id,
            telegram_username=f"web_{req.attendee_id}", attendee_id=req.attendee_id,
        )
        return {"reply": f"🤖 Complaint logged. Category: {row.get('category')}, Severity: {row.get('severity','medium').capitalize()}."}
    elif intent == "feedback" and confidence >= 0.70:
        try:
            save_feedback(req.attendee_id, req.message)
        except Exception:
            pass
        return {"reply": "🙏 Thank you for your feedback!"}
    else:
        try:
            answer = await answer_question(req.message)
            return {"reply": answer}
        except Exception:
            return {"reply": "🤔 I couldn't find info on that. Please ask event staff!"}

@app.post("/api/participant/upload_wall")
async def participant_upload_wall(req: UploadWallPhotoRequest):
    try:
        import base64
        from agents.social_wall_agent import ai_moderate_image
        from tools.supabase_tool import _client

        image_bytes = base64.b64decode(req.image_base64)
        is_safe, reason = await ai_moderate_image(image_bytes)
        if not is_safe:
            raise HTTPException(status_code=400, detail=f"Photo rejected: {reason}")

        # Upload to Cloudinary directly (no separate tool needed)
        raw_url = ""
        try:
            import cloudinary
            import cloudinary.uploader
            from config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET,
            )
            upload_result = cloudinary.uploader.upload(
                image_bytes,
                folder="website_uploads",
                public_id=f"wall_{req.attendee_id}",
                overwrite=False,
            )
            raw_url = upload_result.get("secure_url", "")
        except Exception as cloud_err:
            print(f"[Wall] Cloudinary upload failed: {cloud_err}")

        _client().table("wall_photos").insert({
            "attendee_id": req.attendee_id, "sender_name": req.sender_name,
            "status": "pending", "event_id": req.event_id,
            "file_url": raw_url, "original_url": raw_url,
        }).execute()
        return {"status": "success", "message": "Photo pending moderation."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
