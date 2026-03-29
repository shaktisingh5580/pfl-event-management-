"""
run_bot.py — Standalone bot runner with self-diagnostics.
Run this instead of main.py option [4] for cleaner startup.

Usage:  python run_bot.py
"""
import sys
import os

print("=" * 55)
print("  Aayam 2026 Telegram Bot — Diagnostic Startup")
print("=" * 55)

# ── 1. Check Python path ──────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 2. Check env vars ─────────────────────────────────────
try:
    from config import (
        TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
        EVENT_NAME, EVENT_DATE, EVENT_VENUE
    )
    print(f"✅ Config loaded")
    print(f"   Event   : {EVENT_NAME}")
    print(f"   Date    : {EVENT_DATE}")
    print(f"   Venue   : {EVENT_VENUE}")

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is missing from .env!")
        sys.exit(1)
    print(f"   Token   : {TELEGRAM_BOT_TOKEN[:12]}...{TELEGRAM_BOT_TOKEN[-4:]}")

    if not SUPABASE_URL:
        print("⚠️  SUPABASE_URL not set — DB features will be disabled")
    else:
        print(f"   Supabase: {SUPABASE_URL[:35]}...")

except Exception as e:
    print(f"❌ Config error: {e}")
    sys.exit(1)

# ── 3. Check dependencies ─────────────────────────────────
print()
deps = [
    ("telegram", "python-telegram-bot"),
    ("qrcode",   "qrcode[pil]"),
    ("PIL",      "Pillow"),
    ("supabase", "supabase"),
]
all_ok = True
for mod, pkg in deps:
    try:
        __import__(mod)
        print(f"✅ {pkg}")
    except ImportError:
        print(f"❌ {pkg} — install with: pip install {pkg}")
        all_ok = False

if not all_ok:
    print("\nRun: pip install python-telegram-bot qrcode[pil] Pillow supabase")
    sys.exit(1)

# ── 4. Quick Supabase connectivity test ───────────────────
print()
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        r = sb.table("attendees").select("id").limit(1).execute()
        print(f"✅ Supabase connected ({len(r.data)} row sample)")
    except Exception as e:
        print(f"⚠️  Supabase connection issue: {e}")
        print("   Bot will still run but DB features may be limited")
else:
    print("⚠️  Supabase not configured — DB features disabled")

# ── 5. Start the bot ──────────────────────────────────────
print()
print("=" * 55)
print("  🤖 Starting bot... Press Ctrl+C to stop.")
print("=" * 55)
print()

try:
    from bot.telegram_bot import main
    main()
except KeyboardInterrupt:
    print("\n👋 Bot stopped.")
except Exception as e:
    import traceback
    print(f"\n❌ Bot crashed: {e}")
    traceback.print_exc()
    print("\n── Common fixes ─────────────────────────────────────")
    print("• Wrong token → check TELEGRAM_BOT_TOKEN in .env")
    print("• Another bot instance running → close other terminal windows")
    print("• Supabase error → check SUPABASE_SERVICE_ROLE_KEY in .env")
