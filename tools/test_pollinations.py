import os
import requests
from io import BytesIO
from PIL import Image

POLLINATIONS_API_KEY = "sk_9mxQSClAU0O5z2wFWpemufb84bStoG3V"

def test_generate_poster():
    print("🎨 Testing Pollinations.AI Poster Generation...")
    
    # Simple prompt
    prompt = "A futuristic cyberpunk hackathon poster background, dark blue and purple neon colors, highly detailed, empty space in the middle for text"
    
    # Provide the simplest possible URL string to avoid parameter interpretation errors by their server
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
    
    headers = {
        "Authorization": f"Bearer {POLLINATIONS_API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print(f"📡 Sending request to {url} ...")
    try:
        response = requests.get(url, headers=headers, timeout=120)
        
        if response.status_code == 200:
            print("✅ Successfully got image from Pollinations.AI")
            
            os.makedirs("outputs/branding", exist_ok=True)
            output_path = "outputs/branding/test_raw_poster.png"
            
            image = Image.open(BytesIO(response.content))
            image.save(output_path)
            print(f"💾 Raw poster saved to: {output_path}")
            
            print(f"🖼️ Image size: {image.size}")
            print(f"🖼️ Image format: {image.format}")
            return True
        else:
            print(f"❌ Error: Pollinations API returned status {response.status_code}")
            print(response.text)
            
            # Let's try one more time WITHOUT the Authorization header as a fallback test
            print("\n🔄 Retrying WITHOUT API key (using public endpoint)...")
            pub_response = requests.get(url, headers={"User-Agent": headers["User-Agent"]}, timeout=120)
            if pub_response.status_code == 200:
                 print("✅ Successfully got image from public endpoint!")
                 return True
            else:
                 print(f"❌ Public endpoint also failed: {pub_response.status_code}")
            
            return False
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return False

if __name__ == "__main__":
    test_generate_poster()
