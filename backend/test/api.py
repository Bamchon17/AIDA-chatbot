import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)

data = response.json()

if "error" in data:
    print(f"❌ API Error: {data['error']['message']}")
    print(f"Status: {data['error']['status']}")
elif "models" in data:
    print("✅ รายชื่อ Model ที่คุณใช้ได้:")
    for m in data["models"]:
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print(f" - {m['name']}")
else:
    print("❓ ไม่พบข้อมูลในรูปแบบที่คาดหวัง:")
    print(data)