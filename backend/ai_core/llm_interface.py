import os
import re
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()


class LLMInterface:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("[ERROR] GEMINI_API_KEY not found in .env file")

        # Paid Tier — อัปเดตรายชื่อโมเดลให้ตรงกับเวอร์ชัน Stable ปี 2026
        self.models_to_try = [
            "gemini-2.5-flash",         # หลัก — Stable เร็ว รองรับ 1M tokens
            "gemini-2.5-flash-lite",    # fallback 1 — เน้นความเร็ว
            "gemini-2.5-pro",           # fallback 2 — ตัวท็อปสำหรับงานซับซ้อน
        ]
        self.retry_wait = 25

    def _call_api(self, model_name: str, prompt: str) -> dict:
        url = (
            f"https://generativelanguage.googleapis.com/v1/models/"
            f"{model_name}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2
                # เอา responseMimeType ออกเพื่อป้องกัน HTTP 400 Invalid Payload
            }
        }
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    def _build_entity_context(self, entities: dict) -> str:
        """แปลง entities → ข้อความเสริมใน Prompt"""
        parts = []
        if entities.get("curriculum_year"):
            parts.append(f"ปีหลักสูตร: {entities['curriculum_year']}")
        if entities.get("year"):
            parts.append(f"ชั้นปีที่: {entities['year']}")
        if entities.get("semester"):
            parts.append(f"เทอม: {entities['semester']}")
        if entities.get("course_code"):
            parts.append(f"รหัสวิชา: {entities['course_code']}")
        if entities.get("keywords"):
            parts.append(f"คำสำคัญ: {', '.join(entities['keywords'])}")
        return "  ".join(parts) if parts else "ไม่มีข้อมูลเพิ่มเติม"

    def generate_response(
        self,
        query: str,
        retrieval_results: list,
        intent_result: dict,
        sentiment: str = "normal"
    ) -> dict | None:
        """
        สร้างคำตอบจาก Gemini โดยใช้ context จาก RAG + intent_result ทั้งก้อน

        Args:
            query            : คำถามดิบจาก user
            retrieval_results: list of {"text": str, "score": float} จาก RAGHandler
            intent_result    : dict ทั้งก้อนจาก ThaiIntentClassifier.predict()
            sentiment        : sentiment string

        Returns:
            dict JSON output หรือ None ถ้า API ล้มทุก model
        """
        intent_info  = intent_result.get("intent", {})
        entities     = intent_result.get("entities", {})
        display_name = intent_info.get("display_name", "ทั่วไป")
        confidence   = intent_info.get("confidence", 0.0)

        # Context จาก RAG
        if retrieval_results:
            context_text = "\n\n".join(
                f"[{i}] {res['text']}"
                for i, res in enumerate(retrieval_results, 1)
            )
        else:
            context_text = "ไม่พบข้อมูลในระบบฐานข้อมูล"

        entity_context = self._build_entity_context(entities)

        prompt = f"""Role: AIDA (AI Mascot of Faculty of Engineering, AI & Data Science Major, Bangkok University)
ลักษณะ: น้องสาวที่น่ารัก เป็นกันเอง ให้ข้อมูลถูกต้องและพูดตรงประเด็น

--- Context จาก Knowledge Base ---
หมวดหมู่: {display_name}
{context_text}
--- End of Context ---

--- ข้อมูลที่ระบุเพิ่มเติมในคำถาม ---
{entity_context}

--- คำถามจาก User ---
"{query}"

Intent: {display_name} (confidence: {confidence:.2f})
Sentiment: {sentiment}

Instructions:
1. ตอบโดยอิงจาก Context เท่านั้น ห้ามคิดหรือสร้างข้อมูลเอง (Zero Hallucination)
2. ใช้ข้อมูลเพิ่มเติม (ปีหลักสูตร / รหัสวิชา / ชั้นปี) เพื่อตอบให้เจาะจงขึ้น
3. ถ้า Context ไม่มีข้อมูล ให้บอกตรงๆ อย่างสุภาพ
4. เลือก Emotion ที่เหมาะสม 1 อย่างเท่านั้น จาก 3 ตัวเลือกนี้:
   - "Normal"  : ยังไม่มีใครพูดอะไร หรือทักทายเบื้องต้น
   - "Talking" : กำลังพูดให้ข้อมูล อธิบาย หรือแนะนำ
   - "Curious" : ไม่พบข้อมูล ตอบไม่ได้ หรือต้องการข้อมูลเพิ่มเติม
5. data_type:
   - "fact"  = ข้อมูลดึงตรงจาก Context
   - "logic" = AI วิเคราะห์/สรุปเอง หรือไม่พบข้อมูล
6. speech_text: ต้องอ่านออกเสียงได้ ห้ามมี * # | bullet และห้ามมีตัวย่อที่อ่านไม่ออก

Return ONLY raw JSON ไม่มี markdown ไม่มี code block:
{{
    "display_text": "คำตอบแสดงบนหน้าจอ (ภาษาไทย)",
    "speech_text": "คำตอบสำหรับ TTS อ่านออกเสียง (ภาษาไทย ไม่มีสัญลักษณ์)",
    "emotion": "Normal/Talking/Curious",
    "response_metadata": {{
        "data_type": "fact/logic",
        "confidence_score": 0.0
    }}
}}"""

        for model in self.models_to_try:
            try:
                result_json = self._call_api(model, prompt)
                candidates  = result_json.get("candidates", [])
                if not candidates:
                    print(f"[LLM] {model}: no candidates returned")
                    continue

                text_response = candidates[0]["content"]["parts"][0]["text"]
                text_response = text_response.replace("```json", "").replace("```", "").strip()

                json_match = re.search(r"\{.*\}", text_response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                else:
                    print(f"[LLM] {model}: ไม่พบ JSON ใน response")

            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    delay_match = re.search(r"retry in (\d+)", err_str)
                    wait_sec    = int(delay_match.group(1)) + 2 if delay_match else self.retry_wait
                    print(f"[LLM] {model}: quota exceeded → รอ {wait_sec}s ก่อนลอง model ถัดไป")
                    time.sleep(wait_sec)
                elif "403" in err_str:
                    print(f"[LLM] {model}: PERMISSION_DENIED (Free Tier) → ข้ามทันที")
                else:
                    print(f"[LLM Warning] {model} failed: {e}")
                continue

        print("[LLM Error] ทุก model ล้มเหลว — ตรวจสอบ GEMINI_API_KEY หรือรอ quota reset (07:00 น. ไทย)")
        return None