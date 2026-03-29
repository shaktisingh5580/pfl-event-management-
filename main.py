"""
main.py — Single entry point for the AI Event Management System.
Run: python main.py
"""
import sys
import asyncio
import json
from config import EVENT_NAME, OUTPUTS_DIR

# Fix: Windows asyncio "Event loop is closed" error from Telegram library cleanup
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║        🤖 AI EVENT MANAGEMENT SYSTEM                    ║
║           Powered by OpenRouter + Supabase              ║
╚══════════════════════════════════════════════════════════╝
""")


def menu():
    print(f"\n  Current Event: {EVENT_NAME}")
    print("""
  ── PRE-EVENT ───────────────────────────────────────────
  [1] 💬  Run AI Architect  (Interactive Event Builder)
  [2] 📖  Generate Rulebook PDF
  [3] 🎨  Generate Event Poster + Cloudinary Overlay
  [8] 🌐  Deploy Event Website  (GitHub → Vercel)
  [9] 🔄  Redeploy Website       (push local edits → Vercel, no LLM)

  ── BOT ─────────────────────────────────────────────────
  [4] 🤖  Start Telegram Bot  (all live event features)

  ── POST-EVENT ──────────────────────────────────────────
  [5] 🎓  Generate All Certificates
  [6] 📊  Generate Sponsor ROI Report

  ── DATABASE ────────────────────────────────────────────
  [7] 🗄️  Show Supabase migration SQL (paste into Supabase)

  [q] Quit
""")


def run_architect():
    from agents.architect_agent import generate_event_plan, display_plan_summary
    plan = generate_event_plan()
    if plan:
        print("\n" + display_plan_summary(plan))
    # Note: save is handled inside generate_event_plan now


def run_rulebook():
    schedule_path = OUTPUTS_DIR / "schedule.json"
    if not schedule_path.exists():
        print("❌ Run the AI Architect first (option 1) to generate the schedule.")
        return
    from agents.rulebook_agent import generate_rulebook
    plan = json.loads(schedule_path.read_text())
    generate_rulebook(plan)
    print(f"\n✅ Rulebook saved to: {OUTPUTS_DIR / 'rulebooks' / 'rulebook.pdf'}")


def run_branding():
    schedule_path = OUTPUTS_DIR / "schedule.json"
    if not schedule_path.exists():
        print("❌ Run the AI Architect first (option 1).")
        return
    from agents.branding_agent import run_branding
    plan = json.loads(schedule_path.read_text())
    url = run_branding(plan)
    print(f"\n✅ Branded poster URL: {url}")


def run_bot():
    print("\n🤖 Starting Telegram Bot... (Ctrl+C to stop)\n")
    from bot.telegram_bot import main as bot_main
    bot_main()


def run_certificates():
    from agents.certificate_agent import run_all_certificates
    print("\nEnter rank mapping as JSON (or press Enter to mark all as 'Participant'):")
    print('Example: {"uuid-1234": "1st Place", "uuid-5678": "Finalist"}')
    raw = input("> ").strip()
    rank_mapping = json.loads(raw) if raw else None
    paths = run_all_certificates(rank_mapping)
    print(f"\n✅ Generated {len(paths)} certificates in {OUTPUTS_DIR / 'certificates'}/")


def run_web_deployer():
    schedule_path = OUTPUTS_DIR / "schedule.json"
    if not schedule_path.exists():
        print("❌ Run the AI Architect first (option 1) to generate the schedule.")
        return
    from agents.web_deployer_agent import run_web_deployer as _deploy
    plan = json.loads(schedule_path.read_text())
    url = _deploy(plan)
    print(f"\n✅ Website live at: {url}")


def show_migration():
    from pathlib import Path
    sql_path = Path(__file__).parent / "supabase_migration.sql"
    print("\n" + "═"*60)
    print("Paste this into: Supabase Dashboard → SQL Editor → New Query")
    print("═"*60 + "\n")
    print(sql_path.read_text())


def main():
    print_banner()
    while True:
        menu()
        choice = input("  Select option: ").strip().lower()

        if choice == "1":
            run_architect()
        elif choice == "2":
            run_rulebook()
        elif choice == "3":
            run_branding()
        elif choice == "4":
            run_bot()
        elif choice == "5":
            run_certificates()
        elif choice == "6":
            print("📊 ROI Report generation coming in Phase 3...")
        elif choice == "7":
            show_migration()
        elif choice == "8":
            run_web_deployer()
        elif choice == "9":
            from agents.web_deployer_agent import redeploy_website
            url = redeploy_website()
            print(f"\n✅ Redeployed → {url}")
        elif choice in ("q", "quit", "exit"):
            print("\n👋 Goodbye!\n")
            sys.exit(0)
        else:
            print("  Invalid option, try again.")


if __name__ == "__main__":
    main()
