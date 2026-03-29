"""
agents/scheduler_agent.py
Announcement Scheduler for PFL Event Management.

Uses APScheduler to auto-send Telegram announcements from schedule.json
at the correct real-world times. Runs inside the same process as the bot
(called from the Telegram bot's startup) or as a standalone background thread.

Features:
  - Load schedule.json and schedule each activity's announcement
  - Sends personalized DM to ALL checked-in attendees (room + time reminder)
  - Sends group blast to the event Telegram group
  - Admin can toggle per-slot announcements via the dashboard
  - Wellness check-in polls at random intervals during the event
  - Works with the FastAPI server (start/stop/status endpoints)
"""
import json
import asyncio
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Callable

from config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    TELEGRAM_GROUP_CHAT_ID, TELEGRAM_ADMIN_CHAT_ID,
    OUTPUTS_DIR, EVENT_NAME, EVENT_DATE
)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    print("[Scheduler] ⚠️  APScheduler not installed. Run: pip install apscheduler")


# ─── Global State ─────────────────────────────────────────────────────────────

_scheduler: "BackgroundScheduler | None" = None
_bot_ref = None  # Will be set at startup by the bot


def set_bot(bot) -> None:
    """Register the Telegram bot instance so scheduler can send messages."""
    global _bot_ref
    _bot_ref = bot


def get_status() -> dict:
    """Return current scheduler status."""
    if _scheduler is None:
        return {"status": "stopped", "jobs": []}
    running = _scheduler.running
    jobs = [
        {
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        }
        for job in _scheduler.get_jobs()
    ]
    return {"status": "running" if running else "stopped", "jobs": jobs}


# ─── Schedule Loading ─────────────────────────────────────────────────────────

def load_schedule() -> list[dict]:
    """Load activities from outputs/schedule.json."""
    path = OUTPUTS_DIR / "schedule.json"
    if not path.exists():
        return []
    plan = json.loads(path.read_text(encoding="utf-8"))
    return plan.get("schedule", [])


def _parse_event_date() -> date:
    """Parse EVENT_DATE from config (format: YYYY-MM-DD)."""
    try:
        return datetime.strptime(EVENT_DATE, "%Y-%m-%d").date()
    except Exception:
        return datetime.today().date()


# ─── Announcement Builders ────────────────────────────────────────────────────

def _build_slot_announcement(slot: dict, minutes_before: int = 10) -> str:
    """Build the Telegram announcement message for a schedule slot."""
    if minutes_before > 0:
        return (
            f"⏰ *Reminder — in {minutes_before} minutes:*\n\n"
            f"📌 *{slot['activity']}*\n"
            f"📍 Location: {slot.get('location', 'TBD')}\n"
            f"🕒 Time: {slot['time']}\n"
            f"👤 Coordinator: {slot.get('coordinator', 'TBD')}\n\n"
            f"_{slot.get('notes', '')}_ \n\n"
            f"— 🤖 PFL Event Bot"
        )
    else:
        return (
            f"🎯 *Starting Now!*\n\n"
            f"📌 *{slot['activity']}*\n"
            f"📍 Location: {slot.get('location', 'TBD')}\n"
            f"👤 Coordinator: {slot.get('coordinator', 'TBD')}\n\n"
            f"_{slot.get('notes', '')}_ \n\n"
            f"— 🤖 PFL Event Bot"
        )


def _build_wellness_poll_questions() -> list[str]:
    return [
        "🌡️ How's the temperature in your room?",
        "😊 How are you feeling right now?",
        "🎯 Is the event going smoothly so far?",
        "🍕 Did you get enough food/refreshments?",
        "📶 Is the WiFi/internet working well?",
    ]


# ─── Job Functions (called by scheduler) ─────────────────────────────────────

def _send_slot_announcement_sync(slot: dict, minutes_before: int = 10) -> None:
    """Sync wrapper for async Telegram send — called by APScheduler."""
    if _bot_ref is None:
        print(f"[Scheduler] Bot not set — cannot send announcement for {slot['activity']}")
        return

    msg = _build_slot_announcement(slot, minutes_before)

    async def _send():
        try:
            # Group blast
            if TELEGRAM_GROUP_CHAT_ID:
                await _bot_ref.send_message(
                    chat_id=TELEGRAM_GROUP_CHAT_ID,
                    text=msg,
                    parse_mode="Markdown",
                )
            # DM to all checked-in attendees
            from tools.supabase_tool import get_checked_in_attendees
            attendees = get_checked_in_attendees()
            sent = 0
            for a in attendees:
                if a.get("telegram_id"):
                    try:
                        await _bot_ref.send_message(
                            chat_id=a["telegram_id"],
                            text=msg,
                            parse_mode="Markdown",
                        )
                        sent += 1
                    except Exception:
                        pass
            print(f"[Scheduler] 📢 '{slot['activity']}' announcement sent to {sent} attendees")
        except Exception as e:
            print(f"[Scheduler] Error sending announcement: {e}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def _send_wellness_poll_sync() -> None:
    """Send a random wellness poll to the event group."""
    import random
    if _bot_ref is None:
        return

    questions = _build_wellness_poll_questions()
    question = random.choice(questions)

    async def _poll():
        try:
            if TELEGRAM_GROUP_CHAT_ID:
                await _bot_ref.send_poll(
                    chat_id=TELEGRAM_GROUP_CHAT_ID,
                    question=question,
                    options=["😊 Great!", "😐 Okay", "😕 Issues", "🆘 Need Help"],
                    is_anonymous=False,
                )
                print(f"[Scheduler] 📊 Wellness poll sent: {question}")
        except Exception as e:
            print(f"[Scheduler] Wellness poll failed: {e}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_poll())
        else:
            loop.run_until_complete(_poll())
    except RuntimeError:
        asyncio.run(_poll())


# ─── Scheduler Control ────────────────────────────────────────────────────────

def start_scheduler(
    bot=None,
    skip_slots: list[str] | None = None,
    wellness_interval_mins: int = 90,
) -> dict:
    """
    Start the APScheduler background scheduler.

    Args:
        bot: Telegram bot instance
        skip_slots: List of activity names to skip auto-announcing
        wellness_interval_mins: How often (minutes) to send wellness polls (0 to disable)

    Returns:
        Status dict
    """
    global _scheduler, _bot_ref

    if not HAS_APSCHEDULER:
        return {"status": "error", "message": "APScheduler not installed. Run: pip install apscheduler"}

    if _scheduler and _scheduler.running:
        return {"status": "already_running", "jobs": len(_scheduler.get_jobs())}

    if bot:
        _bot_ref = bot

    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    event_date = _parse_event_date()
    schedule = load_schedule()
    skip_slots = skip_slots or []
    jobs_added = 0

    for slot in schedule:
        if slot.get("activity") in skip_slots:
            continue

        try:
            h, m = slot["time"].split(":")
            hour, minute = int(h), int(m)

            # 10-min reminder
            reminder_minute = minute - 10
            reminder_hour = hour
            if reminder_minute < 0:
                reminder_minute += 60
                reminder_hour = (hour - 1) % 24

            job_id_reminder = f"reminder_{slot['activity'][:20].replace(' ', '_')}"
            _scheduler.add_job(
                _send_slot_announcement_sync,
                trigger=CronTrigger(
                    year=event_date.year, month=event_date.month, day=event_date.day,
                    hour=reminder_hour, minute=reminder_minute,
                ),
                id=job_id_reminder,
                name=f"Reminder: {slot['activity']}",
                args=[slot, 10],
                misfire_grace_time=300,
                replace_existing=True,
            )

            # On-time announcement
            job_id_start = f"start_{slot['activity'][:20].replace(' ', '_')}"
            _scheduler.add_job(
                _send_slot_announcement_sync,
                trigger=CronTrigger(
                    year=event_date.year, month=event_date.month, day=event_date.day,
                    hour=hour, minute=minute,
                ),
                id=job_id_start,
                name=f"Start: {slot['activity']}",
                args=[slot, 0],
                misfire_grace_time=300,
                replace_existing=True,
            )
            jobs_added += 2
        except Exception as e:
            print(f"[Scheduler] Failed to schedule '{slot.get('activity')}': {e}")

    # Wellness polls
    if wellness_interval_mins > 0:
        _scheduler.add_job(
            _send_wellness_poll_sync,
            trigger=IntervalTrigger(minutes=wellness_interval_mins),
            id="wellness_poll",
            name="Wellness Poll",
            misfire_grace_time=600,
            replace_existing=True,
        )
        jobs_added += 1

    _scheduler.start()
    print(f"[Scheduler] ✅ Started with {jobs_added} jobs (date: {event_date})")
    return {"status": "started", "jobs_scheduled": jobs_added, "event_date": str(event_date)}


def stop_scheduler() -> dict:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[Scheduler] 🛑 Stopped")
        return {"status": "stopped"}
    return {"status": "was_not_running"}


def schedule_custom_blast(
    message: str,
    at_time: str,
    job_id: str = "custom_blast",
    target: str = "both",  # "group", "dms", "both"
) -> bool:
    """
    Schedule a one-off custom message at a specific time today.

    Args:
        message: Message text (Markdown)
        at_time: "HH:MM" string (today's date is assumed)
        job_id: Unique ID for this job
        target: "group", "dms", or "both"
    """
    global _scheduler

    if not _scheduler or not _scheduler.running:
        return False

    event_date = _parse_event_date()
    try:
        h, m = at_time.split(":")

        async def _custom():
            if target in ("group", "both") and TELEGRAM_GROUP_CHAT_ID:
                await _bot_ref.send_message(chat_id=TELEGRAM_GROUP_CHAT_ID, text=message, parse_mode="Markdown")
            if target in ("dms", "both"):
                from tools.supabase_tool import get_checked_in_attendees
                for a in get_checked_in_attendees():
                    if a.get("telegram_id"):
                        try:
                            await _bot_ref.send_message(chat_id=a["telegram_id"], text=message, parse_mode="Markdown")
                        except Exception:
                            pass

        def _run():
            try:
                asyncio.run(_custom())
            except Exception as e:
                print(f"[Scheduler] Custom blast error: {e}")

        _scheduler.add_job(
            _run,
            trigger=CronTrigger(
                year=event_date.year, month=event_date.month, day=event_date.day,
                hour=int(h), minute=int(m),
            ),
            id=job_id,
            name=f"Custom: {message[:30]}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        print(f"[Scheduler] Custom blast scheduled at {at_time}")
        return True
    except Exception as e:
        print(f"[Scheduler] Failed to schedule custom blast: {e}")
        return False
