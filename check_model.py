from google import genai
import config

client = genai.Client(api_key=config.GEMINI_API_KEY)

print("🔍 Checking available AI models for your Key...")
print("------------------------------------------------")

try:
    for m in client.models.list():
        if 'generateContent' in m.supported_actions:
            print(f"✅ AVAILABLE: {m.name}")
    print("------------------------------------------------")
    print("Use one of the names above in med_vision.py's models_to_try list.")

except Exception as e:
    print(f"❌ Error: {e}")
