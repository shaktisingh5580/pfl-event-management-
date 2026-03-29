# Frontend Dashboard Prompt

> **Copy-paste this entire prompt to the other AI agent.**

---

## THE PROMPT:

```
Build me a modern, premium organizer dashboard and participant portal web application for an AI-powered Event Management System called "AutoEvent". The backend API is already fully built and running at http://localhost:8000. The frontend should be a Next.js (App Router) project with TypeScript and Tailwind CSS.

═══════════════════════════════════════════════════
 DESIGN REQUIREMENTS
═══════════════════════════════════════════════════

- Dark mode with a deep indigo/violet accent (#6D28D9) and glass-morphism cards
- Sidebar navigation with collapsible sections for each phase
- Responsive: works on desktop + tablet
- Use shadcn/ui components (Button, Card, Dialog, Table, Badge, Tabs, Toast)
- Use recharts for any charts/graphs
- Use lucide-react for icons
- Every API call should show a loading spinner and toast on error
- The API base URL should be configurable via NEXT_PUBLIC_API_URL env var (default: http://localhost:8000)

═══════════════════════════════════════════════════
 PAGE STRUCTURE (Sidebar Navigation)
═══════════════════════════════════════════════════

The dashboard has 3 main phases:

### Phase 1: PRE-EVENT
1. **AI Architect Chat** — Chat with the AI to generate the event plan
2. **Pipeline Status** — See the status of poster/website/sponsors generation
3. **Event Plan Viewer** — View and edit the generated JSON plan
4. **Poster Gallery** — View the generated poster and download it
5. **Sponsors** — List sponsors, preview email, send blast
6. **Website** — Deploy, redeploy, or edit the event website via AI chat

### Phase 2: DURING-EVENT
7. **Check-In Dashboard** — Live list of checked-in attendees (auto-refresh)
8. **Complaints Panel** — See all complaints with severity badges, resolve them
9. **Feedback Stream** — Live feed of attendee feedback
10. **AI Concierge** — Test the event Q&A bot from the dashboard
11. **Social Wall** — View approved/pending wall photos
12. **Matchmaking** — Trigger matchmaking, see computed matches
13. **Scheduler** — Start/stop the announcement scheduler, schedule custom blasts
14. **Bot Control** — Start/Stop the Telegram bot from the dashboard

### Phase 3: POST-EVENT
15. **Certificates** — Generate and send certificates with rank mapping
16. **ROI Report** — Generate the post-event PDF report
17. **Feedback Summary** — View all feedback collected

═══════════════════════════════════════════════════
 COMPLETE API REFERENCE
═══════════════════════════════════════════════════

All endpoints return JSON. The API uses FastAPI with CORS enabled for all origins.

─── HEALTH ───
GET  /                              → { status, service, event_name }

─── REGISTRATION ───
GET  /api/registration-fields       → { standard_fields[], custom_fields[], event_name }
POST /api/register                  → Body: { name, email, password, phone, college, department, year_of_study, telegram_username, skills, interests, goals, team_preference, event_id, dynamic_fields: {} }

─── TEMPLATES ───
GET  /api/templates                 → { templates[] }
GET  /api/templates/{template_id}   → single template object

─── AI ARCHITECT ───
POST /api/architect/chat            → Body: { message, session_id, template_id?, event_id? }
                                      Returns: { reply, finalized, plan?, session_id, pipeline_started }
DELETE /api/architect/session/{id}  → clears session

─── PLAN ───
GET  /api/plan                      → { plan: {...} }
PUT  /api/plan                      → Body: entire plan JSON → { status: "updated" }

─── PIPELINE ───
GET  /api/pipeline/status           → { pipeline: { plan, poster, website, sponsors, scheduler } }
POST /api/pipeline/rerun/{step}     → step = "poster" | "website" | "sponsors"

─── BRANDING ───
POST /api/branding/generate         → Body: { website_url? } → { poster_path, filename }
GET  /api/branding/poster           → Returns PNG file directly (FileResponse)

─── SPONSORS ───
GET  /api/sponsors?event_type_id=techfest&limit=20    → { sponsors[], tiers[] }
GET  /api/sponsors/call-list?event_type_id=techfest    → { call_list[] }
POST /api/sponsors/preview-email    → Body: { sponsor_company, event_type_id, organizer_name, organizer_email, organizer_phone }
POST /api/sponsors/send-emails      → Body: { event_type_id, selected_companies[], from_email, smtp_password, organizer_name, organizer_phone }

─── WEBSITE ───
POST /api/deploy                    → Body: { plan: {} } → { url }
POST /api/deploy/redeploy           → no body → { url }
POST /api/website/generate          → Body: { messages_history[], current_code } → { html }

─── KNOWLEDGE BASE ───
POST /api/knowledge-base/upload     → Multipart: file (PDF) + description → { filename }

─── SCHEDULER (During-Event) ───
GET  /api/scheduler/status          → { running, jobs[] }
POST /api/scheduler/start           → Body: { skip_slots[], wellness_interval_mins } → status
POST /api/scheduler/stop            → no body → status
POST /api/scheduler/blast           → Body: { message, at_time, job_id?, target? }

─── COMPLAINTS (During-Event) ───
GET  /api/complaints?status=&severity=&limit=50    → { complaints[], total }
POST /api/complaints/{complaint_id}/resolve         → Body: { resolved_by? } → { status, id }

─── FEEDBACK (During-Event) ───
GET  /api/feedback?limit=50         → { feedback[], total }

─── CONCIERGE (During-Event) ───
POST /api/concierge/ask?question=   → { question, answer }

─── WALL PHOTOS (During-Event) ───
GET  /api/wall-photos?status=approved&limit=50      → { photos[], total }

─── CHECKED-IN ATTENDEES (During-Event) ───
GET  /api/attendees/checked-in      → { attendees[], total }

─── MATCHMAKING (During-Event) ───
POST /api/matchmaking/run?meeting_point=            → { status, attendees_processed, matches[] }

─── BOT MANAGEMENT ───
GET  /api/bot/status                → { status: "running" | "stopped" }
POST /api/bot/start                 → { status: "started" | "already_running" }
POST /api/bot/stop                  → { status: "stopped" }

─── CERTIFICATES (Post-Event) ───
POST /api/certificates/generate     → Body: { rank_mapping: {} } → { certificates_generated }
POST /api/certificates/send-all     → Body: { rank_mapping: {} } → { count, message }
POST /api/certificates/send-feedback → { message }

─── REPORTS (Post-Event) ───
POST /api/reports/roi               → Returns PDF file directly

─── PARTICIPANT ENDPOINTS ───
POST /api/participant/login         → Body: { email, password, event_id } → { user }
POST /api/participant/chat          → Body: { message, attendee_id, telegram_id?, event_id? } → { reply }
POST /api/participant/upload_wall   → Body: { image_base64, attendee_id, sender_name, event_id? }

═══════════════════════════════════════════════════
 PAGE DETAILS
═══════════════════════════════════════════════════

### 1. AI Architect Chat Page
- Chat interface (like ChatGPT) with message bubbles
- Template selector dropdown at the top (GET /api/templates)
- When plan is finalized, show the plan JSON in a collapsible card and a "View Pipeline" button
- Auto-poll GET /api/pipeline/status every 3 seconds when pipeline is running
- Show pipeline status as a horizontal stepper (Plan → Poster → Website → Sponsors)

### 2. Check-In Dashboard
- GET /api/attendees/checked-in — auto-refresh every 10 seconds
- Show a large counter badge at the top: "✅ 47 / 200 Checked In"
- Table with columns: Name, Email, Seat, Coordinator, Check-In Time, Dynamic Fields
- Dynamic fields should render as small badges (e.g., "Team: Kings XI")
- Search bar to filter by name

### 3. Complaints Panel
- GET /api/complaints — filterable by severity (Low/Medium/High/Emergency) and status (open/resolved)
- Each complaint is a card showing: category badge, severity color dot, message text, reporter name, timestamp
- "Resolve" button on each card → POST /api/complaints/{id}/resolve
- Severity color coding: Low=🟡, Medium=🟠, High=🔴, Emergency=‼️

### 4. Feedback Stream
- GET /api/feedback — show as a timeline/stream of cards
- Each card: feedback text, attendee name (if available), timestamp
- Optional: sentiment indicator (positive/negative) based on text length or keywords

### 5. AI Concierge Test
- Simple chat input box: type a question, hit send
- POST /api/concierge/ask?question=...
- Shows the AI answer below
- Useful for organizers to test what attendees will see

### 6. Social Wall
- GET /api/wall-photos — show as a masonry grid of photo cards
- Each card: photo thumbnail (from file_url), sender name, status badge (approved/pending), timestamp
- Tabs: "Approved" | "Pending" | "All"

### 7. Matchmaking
- POST /api/matchmaking/run → show results as a table
- Each row: Person Name, Match 1 (score), Match 2 (score), Match 3 (score)
- Input field for "Meeting Point" (default: "the Networking Zone")

### 8. Scheduler
- GET /api/scheduler/status — show running/stopped badge + list of scheduled jobs
- Start/Stop buttons → POST /api/scheduler/start / POST /api/scheduler/stop
- "Custom Blast" form: message text, time (datetime picker), target (group/DMs/both)

### 9. Bot Control
- GET /api/bot/status — show running/stopped with a big toggle button
- POST /api/bot/start / POST /api/bot/stop

### 10. Certificate Generator (Post-Event)
- Form: rank_mapping JSON editor (key = attendee_id, value = "1st" / "2nd" / "3rd" / "Participation")
- "Generate" button → POST /api/certificates/generate
- "Send All via Telegram" button → POST /api/certificates/send-all
- Show count of generated certificates

### 11. ROI Report
- "Generate Report" button → POST /api/reports/roi → download the PDF

═══════════════════════════════════════════════════
 ENV VARIABLES
═══════════════════════════════════════════════════

Create a .env.local with:
NEXT_PUBLIC_API_URL=http://localhost:8000

═══════════════════════════════════════════════════
 IMPORTANT NOTES
═══════════════════════════════════════════════════

1. The backend is ALREADY running. You do NOT need to build any backend code.
2. CORS is already enabled on the backend for all origins.
3. All POST endpoints accept JSON body unless specified as multipart (only /api/knowledge-base/upload).
4. The /api/branding/poster and /api/reports/roi endpoints return binary files, not JSON.
5. The /api/architect/chat endpoint is stateful per session_id — maintain session_id across messages.
6. Use SWR or React Query for data fetching with auto-refresh on the during-event pages.
7. For the AI Architect chat, use streaming or polling — the response may take 5-15 seconds.
8. Initialize the project in the current directory ./
9. Make sure the design is PREMIUM — dark mode, glassmorphism, smooth transitions, hover effects.
```

---

> [!TIP]
> Copy everything between the ``` code fences above and paste it to the other agent.
