import google.generativeai as genai
import config
from PIL import Image

# Setup
genai.configure(api_key=config.GEMINI_API_KEY)

# Create a dummy image (100x100 white) to test vision
img = Image.new('RGB', (100, 100), color = 'white')

# The Master List of potential models
candidates = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite-preview-02-05",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-002",
    "gemini-pro",
    "gemini-pro-vision"
]

print("🔎 STARTING LIVE CONNECTION TEST...")
print("-----------------------------------")

working_model = None

for model_name in candidates:
    print(f"👉 Testing: {model_name} ...", end=" ")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(["Test", img])
        print("✅ SUCCESS!")
        working_model = model_name
        break # We found a winner!
    except Exception as e:
        print("❌ FAILED")
        error_msg = str(e)
        if "404" in error_msg:
            print("   (Reason: Model not found for your key)")
        elif "429" in error_msg:
            print("   (Reason: Quota limit reached/Zero)")
        else:
            print(f"   (Reason: {error_msg[:50]}...)")

print("-----------------------------------")
if working_model:
    print(f"🏆 WINNER: {working_model}")
    print("Update med_vision.py to use ONLY this name.")
else:
    print("💀 FATAL: No models worked. Check your API Key billing status.")