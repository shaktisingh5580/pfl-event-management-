"""
agents/branding_agent.py
AI Branding — generates event posters via Pollinations.AI (free, no key needed)
and applies Cloudinary dynamic overlays (date, venue, QR code).
"""
import requests
import urllib.parse
from pathlib import Path
from config import (
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
    EVENT_NAME, EVENT_DATE, EVENT_VENUE, EVENT_HASHTAG, EVENT_WEBSITE_URL,
    OUTPUTS_DIR, ASSETS_DIR
)


def generate_poster(event_plan: dict) -> Path:
    """
    Generates a themed event poster using Pollinations.AI (free, no API key).
    Downloads and saves to outputs/posters/poster.png.
    """
    theme = event_plan.get("theme", "technology")
    event_type = event_plan.get("event_type", "hackathon")
    event_name = event_plan.get("event_name", EVENT_NAME)

    # Craft a cinematic prompt for a stunning poster
    prompt = (
        f"Professional event poster for '{event_name}', a college {event_type}. "
        f"Theme: {theme}. "
        "Dark futuristic background with neon blue and purple gradients. "
        "Abstract tech elements, circuit patterns, glowing lines. "
        "Cinematic lighting, ultra-detailed, 4K, no text, no typography. "
        "Suitable as a background for an event promotional poster."
    )

    encoded_prompt = urllib.parse.quote(prompt)
    primary_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1350&nologo=true&seed=42"
    
    print(f"[Branding] Generating poster from Pollinations.AI...")
    
    max_retries = 2
    success = False
    poster_path = OUTPUTS_DIR / "posters" / "poster_base.png"
    poster_path.parent.mkdir(parents=True, exist_ok=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for attempt in range(max_retries):
        try:
            print(f"  -> Attempt {attempt + 1}/{max_retries}...")
            response = requests.get(primary_url, headers=headers, timeout=20)
            if response.status_code == 200:
                poster_path.write_bytes(response.content)
                success = True
                break
            else:
                print(f"  -> API returned {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  -> Attempt {attempt + 1} failed: {e}")
        
        import time
        time.sleep(2)

    if not success:
        print("[Branding] Pollinations.AI is down or timing out. Creating local fallback background...")
        # Fallback: create a local sleek gradient background so the pipeline doesn't crash
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (1080, 1350), color=(15, 15, 25))
        draw = ImageDraw.Draw(img)
        # Draw a simple gradient-like pattern
        for y in range(1350):
            r = int(15 + (y / 1350) * 20)
            g = int(15 + (y / 1350) * 10)
            b = int(25 + (y / 1350) * 40)
            draw.line([(0, y), (1080, y)], fill=(r, g, b))
        
        # Draw some subtle "tech" lines
        for i in range(0, 1080, 100):
            draw.line([(i, 0), (i, 1350)], fill=(30, 30, 50), width=1)
        for i in range(0, 1350, 100):
            draw.line([(0, i), (1080, i)], fill=(30, 30, 50), width=1)

        img.save(poster_path)
        print(f"[Branding] Fallback Base poster saved → {poster_path}")
    else:
        print(f"[Branding] Base poster saved → {poster_path}")

    return poster_path


def apply_local_overlay(poster_path: Path, event_plan: dict, website_url: str = "") -> Path:
    """
    Applies text overlays (Event Name, Date, Venue, Hashtag) locally using Pillow.
    Also embeds the event website QR code in the bottom-right corner.
    100% Free. No API Keys required.
    """
    from PIL import Image, ImageDraw, ImageFont
    import qrcode

    event_name  = event_plan.get("event_name", EVENT_NAME)
    date        = event_plan.get("date", EVENT_DATE)
    venue       = event_plan.get("venue", EVENT_VENUE)
    hashtag     = event_plan.get("hashtag", EVENT_HASHTAG)
    # Use provided URL, fall back to config
    url = website_url or EVENT_WEBSITE_URL or f"https://pfl-events.vercel.app"

    print("[Branding] Applying text overlays + QR code locally using Pillow...")
    
    try:
        img = Image.open(poster_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Try to load a nice font, fallback to default if not available
        try:
            title_font = ImageFont.truetype("arial.ttf", 80)
            subtitle_font = ImageFont.truetype("arial.ttf", 40)
            small_font = ImageFont.truetype("arial.ttf", 22)
        except IOError:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Add a dark gradient overlay at the bottom and center for text readability
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([0, height/2 - 150, width, height/2 + 50], fill=(0, 0, 0, 180))
        overlay_draw.rectangle([0, height - 200, width, height], fill=(0, 0, 0, 200))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # Draw Event Name (Center)
        title_text = event_name.upper()
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (width - tw) / 2
        y = (height / 2) - 100
        draw.text((x + 4, y + 4), title_text, font=title_font, fill=(0, 0, 0, 255))
        draw.text((x, y), title_text, font=title_font, fill=(255, 255, 255, 255))

        # Draw Date & Venue
        subtitle_text = f"{date}    |    {venue}"
        s_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
        stw = s_bbox[2] - s_bbox[0]
        sx = (width - stw) / 2
        sy = y + th + 30
        draw.text((sx + 3, sy + 3), subtitle_text, font=subtitle_font, fill=(0, 0, 0, 255))
        draw.text((sx, sy), subtitle_text, font=subtitle_font, fill=(224, 224, 255, 255))

        # Draw Hashtag (Bottom left, leaving room for QR)
        hy = height - 80
        draw.text((40, hy), hashtag, font=subtitle_font, fill=(167, 139, 250, 255))

        # ── Embed QR code (bottom-right corner) ──────────────────────────────
        try:
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=6,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#A78BFA", back_color="white").convert("RGB")
            qr_size = 180
            qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

            # White background box behind QR
            qr_x = width - qr_size - 30
            qr_y = height - qr_size - 30
            box_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            bd = ImageDraw.Draw(box_overlay)
            bd.rounded_rectangle(
                [qr_x - 10, qr_y - 10, qr_x + qr_size + 10, qr_y + qr_size + 10],
                radius=12, fill=(255, 255, 255, 240)
            )
            img = Image.alpha_composite(img, box_overlay)
            img.paste(qr_img, (qr_x, qr_y))
            draw = ImageDraw.Draw(img)

            # "Scan to Register" label above QR
            label = "Scan to Register"
            lbbox = draw.textbbox((0, 0), label, font=small_font)
            lw = lbbox[2] - lbbox[0]
            lx = qr_x + (qr_size - lw) // 2
            draw.text((lx, qr_y - 28), label, font=small_font, fill=(167, 139, 250, 255))
            print(f"[Branding] QR code embedded → {url}")
        except Exception as qr_err:
            print(f"[Branding] QR embed failed (non-fatal): {qr_err}")

        branded_path = OUTPUTS_DIR / "posters" / "poster_branded.png"
        img.convert("RGB").save(branded_path, format="PNG")
        print(f"[Branding] Branded poster saved → {branded_path}")
        return branded_path

    except Exception as e:
        print(f"[Branding] Error applying overlay: {e}")
        return poster_path


def run_branding(event_plan: dict, website_url: str = "") -> Path:
    """Full pipeline: generate base poster → apply local text overlay + QR code."""
    poster_path = generate_poster(event_plan)
    branded_path = apply_local_overlay(poster_path, event_plan, website_url=website_url)
    return branded_path


if __name__ == "__main__":
    import json
    schedule_path = OUTPUTS_DIR / "schedule.json"
    if schedule_path.exists():
        plan = json.loads(schedule_path.read_text())
        url = run_branding(plan)
        print(f"\n✅ Branded poster: {url}")
    else:
        print("Run architect_agent.py first.")
