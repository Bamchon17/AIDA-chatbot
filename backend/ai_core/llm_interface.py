import os
import json
import requests
import re
from dotenv import load_dotenv

load_dotenv()

class LLMInterface:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("[ERROR] GEMINI_API_KEY not found in .env file")
        
        # ใช้รายชื่อที่ถูกต้องตาม API v1beta
        self.models_to_try = [
            "gemini-2.5-flash",      # ตัวใหม่ล่าสุด (ถ้า Server หายล่มจะไวมาก)
            "gemini-2.0-flash",      # ตัวหลักที่เสถียรสุด
            "gemini-2.0-flash-lite"  # ตัวประหยัดโควตา เผื่อตัวบนเต็ม
        ]

    def _call_api(self, model_name, prompt):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        headers = {'Content-Type': 'application/json'}
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2, # อุณหภูมิต่ำเพื่อให้ตอบตาม Context ไม่มั่ว
                "response_mime_type": "application/json"
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    def generate_response(self, query, retrieval_results, intent="general", sentiment="normal"):
        # 1. รวบรวมข้อมูลบริบทจาก RAG
        context_text = ""
        if retrieval_results:
            for i, res in enumerate(retrieval_results, 1):
                context_text += f"[{i}] {res['text']}\n\n"
        else:
            context_text = "ไม่พบข้อมูลในระบบฐานข้อมูล"

        # 2. สร้าง Prompt 
        prompt = f"""
        Role: AIDA (AI Mascot of Engineering Faculty, AIE Major)
        
        Context Data from Knowledge Base:
        {context_text}
        
        User Query: "{query}"
        User Intent (Mock): {intent}
        User Sentiment (Mock): {sentiment}
        
        Instructions:
        1. Base your answer ONLY on the provided Context Data. Pay close attention to the [หมวดหมู่: ...] tags.
        2. If the context does not contain the answer, politely inform the user that you don't have this information.
        3. Emotion Selection: Choose exactly ONE state based on the context and answer:
           - "Normal" : ทักทายทั่วไป หรือตอบคำถามสั้นๆ
           - "Talking" : อธิบายรายละเอียดยาวๆ หรือให้ข้อมูล
           - "Happy" : ตอบรับเชิงบวก หรือแสดงความยินดี
           - "Curious" : ไม่พบข้อมูล, ระบบขัดข้อง หรือต้องการคำถามเพิ่มเติม
           - "Encouraging" : ให้คำปรึกษา แนะนำแนวทาง หรือให้กำลังใจ
        4. Data Labeling:
           - data_type: "fact" (if data is directly retrieved from Context) OR "logic" (if AI analyzed/calculated or if no data found).
        
        Return Output as RAW JSON format ONLY:
        {{
            "display_text": "Answer for screen display (Thai)",
            "speech_text": "Answer for Text-to-Speech (Thai phonetic reading)",
            "emotion": "Normal/Talking/Happy/Curious/Encouraging",
            "response_metadata": {{
                "data_type": "fact/logic",
                "confidence_score": 0.95
            }}
        }}
        """

        # 3. ส่งคำขอไปยัง LLM API
        for model in self.models_to_try:
            try:
                result_json = self._call_api(model, prompt)
                candidates = result_json.get('candidates', [])
                if not candidates: 
                    continue
                
                text_response = candidates[0]['content']['parts'][0]['text']
                text_response = text_response.replace("```json", "").replace("```", "").strip()
                
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                    
            except Exception as e:
                print(f"[LLM Warning] Model {model} failed: {e}")
                continue

        return None