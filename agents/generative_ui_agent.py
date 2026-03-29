"""
agents/generative_ui_agent.py
Handles v0.dev style continuous AI editing of the event website.
Takes the current HTML, the user's new request, and returns the modified HTML.
"""
import json
import requests
from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

GENERATIVE_UI_PROMPT = """
You are an expert Frontend Web Developer acting as a Continuous Generative UI AI (similar to v0.dev).
The user is viewing a live preview of an HTML/TailwindCSS website, and they are asking you to make modifications to the code.

YOUR TASK:
You will be provided with:
1. The CURRENT HTML CODE of the website.
2. The user's requested CHANGE (which may be part of a longer chat history).

You must return the ENTIRE, fully updated, working HTML code. Do NOT return tiny snippets, and do NOT use markdown formatting outside of a single `html` block.
You MUST retain functionality that is already there (like Supabase registration forms), unless the user specifically asks to remove it.
Use Tailwind CSS classes for all styling. Maintain a high-end, modern, glassmorphism aesthetic.

RETURN YOUR RESPONSE EXACTLY AS VALID HTML Code wrapped in a markdown codeblock.
"""

def generate_code_update(chat_history: list, current_code: str) -> str:
    """
    Takes a conversation history (list of dicts with 'role' and 'content')
    and the current HTML code. Calls the LLM and extracts the updated HTML.
    """
    system_content = GENERATIVE_UI_PROMPT + f"\n\n### CURRENT HTML CODE ###\n{current_code}"
    
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not set.")
        
    system_message = {
        "role": "system",
        "content": system_content
    }
    messages = [system_message] + chat_history

    print(f"[GenerativeUI] Requesting code update from LLM ({LLM_MODEL})...")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.2, # Low temp for code stability
    }

    response = requests.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=90)
    response.raise_for_status()

    llm_response = response.json()["choices"][0]["message"]["content"]

    # Extract the HTML code snippet from the LLM's markdown response
    if "```html" in llm_response:
        new_code = llm_response.split("```html")[1].split("```")[0].strip()
    elif "```" in llm_response:
        new_code = llm_response.split("```")[1].split("```")[0].strip()
    else:
        new_code = llm_response.strip()

    print("[GenerativeUI] Code update generated successfully.")
    return new_code
