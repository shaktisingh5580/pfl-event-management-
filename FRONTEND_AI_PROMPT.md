# Frontend AI Prompt: PFL Event Management Dashboard

You are an expert Next.js and Tailwind frontend developer. Build a stunning, premium SaaS dashboard for **PFL Event Management** — an AI-powered event management platform.

## Brand Identity
- **Company**: PFL Event Management  
- **Tagline**: "Manage Events. Effortlessly."  
- **Primary Colors**: Purple (#a855f7) to Blue (#3b82f6) gradient  
- **Background**: Deep dark `#07070f`  
- **UI Style**: Glassmorphism cards with `backdrop-filter: blur`, subtle glow borders, premium dark aesthetics  
- **Logo**: "PFL" in bold purple gradient at top of sidebar  

---

## 1. Multi-Tenant Architecture & Security
- **Authentication:** Use `@supabase/ssr` for auth. Organizers must log in.
- **Data Fetching:** Direct Supabase queries for CRUD; RLS auto-filters by `auth.uid()`.
- **AI Calls:** POST to Python FastAPI at `http://localhost:8000` — never expose LLM keys on frontend.

---

## 2. API & Database Context

### A. Supabase (DB & Auth)
- Tables: `events`, `attendees`, `wall_photos`, `complaints`, `certificates`, `organizer_files`
- `attendees.dynamic_fields` (JSONB) — custom registration data

### B. Python FastAPI Backend (http://localhost:8000)
All new endpoints available:

```
GET  /api/templates              → list of event templates
POST /api/architect/chat         → {message, session_id, template_id} → {reply, finalized, plan}
GET  /api/pipeline/status        → check auto-triggered pipeline {plan, poster, website, sponsors}
POST /api/pipeline/rerun/{step}  → manually rerun a single step (poster/website/sponsors)
GET  /api/plan                   → get saved event plan JSON
PUT  /api/plan                   → update saved event plan JSON
GET  /api/sponsors?event_type_id → sponsor list
POST /api/sponsors/preview-email → draft email preview
POST /api/sponsors/send-emails   → blast emails
GET  /api/sponsors/call-list     → phone call list
POST /api/branding/generate      → generate poster + QR
GET  /api/branding/poster        → download poster PNG
POST /api/deploy                 → deploy website to Vercel
GET  /api/scheduler/status       → {status, jobs}
POST /api/scheduler/start        → start auto announcements
POST /api/scheduler/stop         → stop scheduler
POST /api/scheduler/blast        → schedule custom blast {message, at_time}
POST /api/certificates/generate  → generate all certificates
POST /api/certificates/send-all  → generate + queue delivery
POST /api/certificates/send-feedback → trigger feedback poll
POST /api/reports/roi            → download ROI PDF
GET  /api/bot/status             → {status: running|stopped}
POST /api/bot/start              → start Telegram bot
POST /api/bot/stop               → stop Telegram bot
```

---

## 3. Sidebar Navigation
```
PFL [logo]
─────────────
  📊 Dashboard        /dashboard
  🎓 Event Planner    /dashboard/planner
  🌐 Website Builder  /dashboard/website
  🎨 Branding         /dashboard/branding
  🤝 Sponsors         /dashboard/sponsors
  👥 Attendees        /dashboard/attendees
  📷 Social Wall      /dashboard/wall
  🆘 Help Desk        /dashboard/complaints
  📅 Schedule         /dashboard/schedule
  🎓 Post-Event       /dashboard/post-event
─────────────
  ⚙️  Settings
  🚪 Logout
```

---

## 4. Required Pages

### A. Overview Dashboard (`/dashboard`)
- Top row: 4 stat cards — Registrations, Checked-In, Complaints (open), Certificates Issued
- Middle: Bot status indicator 🟢/🔴 with Start/Stop buttons
- Scheduler status (running/stopped) + last job info
- Recent activity feed from complaints + wall photos

### B. AI Event Planner (`/dashboard/planner`)
**Before chat starts:** Show template picker with 5 event type cards (fetch from `GET /api/templates`):
- 🎓 TechFest | 💻 Hackathon | 🎭 Cultural Fest | 🏏 Sports Event | 🎤 Conference
- Each card: icon, name, description, "Use This Template" button

**Chat Interface & Automated Pipeline:**
- Gemini-style dark chat UI once template selected or "Start Blank" clicked
- POST `{message, session_id, template_id}` to `/api/architect/chat`
- Show typing indicator during API call
- When `finalized = true`: 
  1. Hide the chat interface
  2. Show a dynamic Loading Screen / Processing Dashboard titled "Orchestrating Event..."
  3. Poll `GET /api/pipeline/status` every 2 seconds
  4. Display live status of the 4 background tasks:
     - 📝 **Event Plan:** Ready!
     - 🎨 **Branding:** Generating poster... -> Done
     - 🌐 **Website:** Deploying to Vercel... -> Done
     - 🤝 **Sponsors:** Matching companies... -> Done
  5. Once all `!= "not_started" && != "running..."`, show a green "✅ Event is live!" banner with quick links to the Poster, Website, and Sponsors tabs.
- Add PDF upload zone for rules/coordinators knowledge base

### B2. Plan Editor (`/dashboard/plan` - New Subpage)
- A clean JSON viewer/editor or structured form to display `GET /api/plan`
- Let the user edit details (e.g., change schedule time from 9 AM to 10 AM)
- "Save Changes" button (`PUT /api/plan`)

### C. Website Builder (`/dashboard/website`)
- Monaco editor (left) + Live iframe preview (right)
- AI chat sidebar: type "change background to darker" → streams updated HTML from `/api/website/generate`
- "Deploy to Vercel →" button → POST `/api/deploy` with current plan
- Show deployed URL with click-to-open and copy button

### D. Branding & Posters (`/dashboard/branding`)
- "Generate Poster with AI" button → POST `/api/branding/generate`
- Show generated poster image with:
  - 🔄 Regenerate button
  - ⬇️ Download PNG button (`GET /api/branding/poster`)
  - ✅ Approve button (marks it ready for sharing)
- Below poster: show embedded QR code preview with text "Scan = Attendee Registration Page"
- Optional: text field to override website URL for QR

### E. Sponsors (`/dashboard/sponsors`)
- Filter bar: Event Type dropdown → fetch sponsors from `GET /api/sponsors?event_type_id=X`
- Table: Company | Industry | Tier badge (Platinum/Gold/Silver/Bronze colored) | Email | Phone | Action
- Multi-select checkboxes on rows
- "Preview Email" button → opens modal with AI-drafted email (POST `/api/sponsors/preview-email`)
- "Send Selected" button → POST `/api/sponsors/send-emails` (needs From Email + App Password input first — show secure input modal)
- Below table: "📞 Call List" accordion showing only companies with phone numbers

### F. Attendees Directory (`/dashboard/attendees`)
- Searchable, sortable data table from Supabase `attendees`
- Show `dynamic_fields` JSONB keys as colorful tags (T-shirt size, event preferences etc.)
- QR scan button to mark check-in (simulated for web — real scan from bot)
- Export CSV button

### G. Social Wall Moderation (`/dashboard/wall`)
- Grid of pending photos (`wall_photos` where `approved = false`)
- Green ✅ / Red ❌ approve/reject buttons
- Live-updating: poll every 5s for new pending photos

### H. Help Desk (`/dashboard/complaints`)
- List of open complaints with colored severity badges
  - 🔴 Emergency | 🟠 High | 🟡 Medium | 🟢 Low
- "Resolve" button patches Supabase row to `status = 'resolved'`
- Complaint category breakdown mini-chart

### I. Schedule & Announcements (`/dashboard/schedule`)
- Timeline view of activities from `schedule.json` (fetched from `/api/scheduler/status`)
- Toggle per slot: "📢 Auto-Announce" switch
- "Test Blast Now" button for each slot → POST `/api/scheduler/blast` with slot time
- Scheduler status card: 🟢 Running / 🔴 Stopped + total jobs
- Start/Stop Scheduler buttons

### J. Post-Event (`/dashboard/post-event`)
Three action cards:
1. **🎓 Certificates**  
   - "Generate All Certificates" → POST `/api/certificates/generate` → show count  
   - "Send via Telegram" → POST `/api/certificates/send-all` with progress indicator  
2. **💬 Feedback**  
   - "Send Feedback Poll" → POST `/api/certificates/send-feedback`  
   - Shows number of responses from Supabase `feedback` table  
3. **📊 ROI Report**  
   - "Generate & Download Report" → POST `/api/reports/roi` → triggers PDF download  
   - Preview panel showing key stats: registrations, check-in rate, wall photos, matches

---

## 5. Bot Control (Every Page — Floating)
- Floating bottom-right bot status pill: 🟢 Bot Running / 🔴 Bot Stopped
- Click to toggle start/stop
- Shows pulse animation when running

---

## 6. Implementation Notes
- Handle loading states on ALL API calls with skeleton loaders or spinners
- Toast notifications for success/error on every action
- The Python FastAPI backend is already built. Build only the Next.js frontend.
- Full creative freedom on aesthetics — make it feel like a premium ₹50k/month SaaS tool
