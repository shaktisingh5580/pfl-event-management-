import time
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_pipeline():
    print("🚀 AutoEvent Full Pipeline Tester")
    print("=================================")
    
    # 1. Check if server is running
    try:
        requests.get(f"{BASE_URL}/")
    except requests.exceptions.ConnectionError:
        print("❌ Error: API Server is not running. Please start it with:")
        print("python -m uvicorn api.server:app --reload --port 8000")
        sys.exit(1)

    # 2. Start Architect Chat
    print("\n[1/3] 🧠 Chatting with AI Architect to generate plan...")
    session_id = f"test-pipeline-{int(time.time())}"
    
    # We clear the session just in case
    requests.delete(f"{BASE_URL}/api/architect/session/{session_id}")

    # Send a prompt that provides all info immediately so it finalizes in 1 turn
    prompt = """
    Hi, I want to organize a college hackathon called "CyberStorm 2026".
    Date: October 15, 2026
    Venue: Engineering Block, GTU Campus
    Theme: Cybersecurity and AI
    Participants expected: 250
    Schedule:
      09:00 - Registration & Breakfast
      10:00 - Opening Ceremony
      11:00 - Hacking Starts
      13:00 - Lunch
      18:00 - Final Pitches
      20:00 - Awards Ceremony
    Resources: 2 main halls, 50 tables, 100 power strips. Need 10 volunteers. Budget is 50,000 INR.
    Rules: Bring your own laptop. Teams of 2-4. 
    Coordinators: Alice (Registration), Bob (Hardware), Charlie (Judging).
    Registration Fields needed: Name, Email, Github Link, Dietary Restrictions.
    Please finalize the plan immediately since I have provided all the required information.
    """

    print("Sending initial prompt to Architect... (this takes ~10-20 seconds)")
    
    # Loop up to 5 times to handle the multi-turn conversational nature
    for i in range(5):
        payload = {
            "message": prompt.strip(),
            "session_id": session_id
        }
        if i == 0:
            payload["template_id"] = "hackathon"
            
        res = requests.post(f"{BASE_URL}/api/architect/chat", json=payload)
        
        if res.status_code != 200:
            print(f"❌ Error communicating with architect: {res.text}")
            sys.exit(1)
            
        data = res.json()
        print(f"\nArchitect Reply (Turn {i+1}):\n{data['reply']}\n")
        
        if data.get("finalized"):
            print("✅ Plan finalized! Orchestration Pipeline should have started in the background.")
            break
            
        # If not finalized, feed it a confirmation prompt to force it to finalize
        prompt = "Yes, all this information is absolute correct and complete. Please do not ask any more questions and FINALIZE_PLAN immediately."
        print("Architect needs more confirmation. Auto-replying: 'Yes...'")
    else:
        print("⚠️ Architect did not finalize the plan after 5 turns.")
        sys.exit(1)
    
    # 3. Poll Pipeline Status
    print("\n[2/3] ⏳ Polling Pipeline Status...")
    start_time = time.time()
    
    while True:
        status_res = requests.get(f"{BASE_URL}/api/pipeline/status")
        if status_res.status_code == 200:
            pipeline = status_res.json().get("pipeline", {})
            
            # Print current state
            print("\r" + " | ".join([f"{k.upper()}: {v}" for k, v in pipeline.items()]), end="", flush=True)
            
            # Check if all are done/error
            all_done = True
            for k, v in pipeline.items():
                if "..." in v or "queued" in v:
                    all_done = False
                    break
                    
            if all_done:
                print("\n\n✅ [3/3] Pipeline Finished!")
                break
                
        time.sleep(2)
        
        if time.time() - start_time > 180:  # 3 min timeout
            print("\n❌ Pipeline timed out after 3 minutes.")
            break

    # 4. View final plan
    print("\n📋 Fetching generated plan from /api/plan...")
    plan_res = requests.get(f"{BASE_URL}/api/plan")
    if plan_res.status_code == 200:
        plan_data = plan_res.json().get("plan", {})
        print(f"Plan Name: {plan_data.get('event_name')}")
        print(f"Plan Date: {plan_data.get('date')}")
        print(f"Plan Venue: {plan_data.get('venue')}")

if __name__ == "__main__":
    test_pipeline()
