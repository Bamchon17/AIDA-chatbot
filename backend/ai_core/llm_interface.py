import os, re, json, time, requests
from dotenv import load_dotenv
load_dotenv()


class LLMInterface:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("[ERROR] GEMINI_API_KEY not found in .env file")
        self.models_to_try = [
            "gemini-2.5-pro",    # หลัก
            "gemini-2.5-flash",  # fallback — ถ้า 2.5-pro JSON fail หรือ 503
        ]
        self.retry_wait = 5

    def _call_api(self, model_name: str, prompt: str) -> dict:
        clean = model_name.replace("models/","")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{clean}:generateContent?key={self.api_key}")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature":0.1,"topP":0.95,"maxOutputTokens":2048}
        }
        r = requests.post(url, headers={"Content-Type":"application/json"},
                          json=payload, timeout=30)
        if r.status_code == 200:
            return r.json()
        raise Exception(f"HTTP {r.status_code}: {r.text}")

    def _build_entity_context(self, entities: dict) -> str:
        parts = []
        if entities.get("curriculum_year"): parts.append(f"ปีหลักสูตร: {entities['curriculum_year']}")
        if entities.get("year"):            parts.append(f"ชั้นปีที่: {entities['year']}")
        if entities.get("semester"):
            sem = entities["semester"]
            parts.append(f"เทอม: {'ฤดูร้อน (Summer)' if sem=='summer' else sem}")
        if entities.get("generation"):      parts.append(f"รุ่น: {entities['generation']}")
        if entities.get("plan"):            parts.append(f"แผน: {entities['plan']}")
        if entities.get("course_code"):     parts.append(f"รหัสวิชา: {entities['course_code']}")
        if entities.get("keywords"):        parts.append(f"คำสำคัญ: {', '.join(entities['keywords'])}")
        if entities.get("generation") and entities.get("plan"):
            gen = entities["generation"]; plan = entities["plan"]
            sem = entities.get("semester","")
            sem_text = " ภาคการศึกษาฤดูร้อน" if sem=="summer" else (f" ภาคการศึกษาที่ {sem}" if sem else "")
            parts.append(f"[ค้นหาใน Context: หัวข้อ '#### รุ่น {gen} (แผน{plan})'{sem_text}]")
        return "  ".join(parts) if parts else "ไม่มีข้อมูลเพิ่มเติม"

    def _parse_json_response(self, text: str) -> dict | None:
        """parse JSON จาก LLM response — robust version"""
        # ลบ markdown fence
        text = text.replace("```json","").replace("```","").strip()

        # ลอง parse ตรง
        try:
            return json.loads(text)
        except Exception:
            pass

        # หา { ... } block ที่ complete ที่สุด (วิธี brace matching)
        start = text.find("{")
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == "{":   depth += 1
                elif ch == "}": depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except Exception:
                        break

        # fallback: regex แบบ greedy
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        return None

    def generate_response(self, query: str, retrieval_results: list,
                          intent_result: dict, sentiment: str = "normal") -> dict | None:
        intent_info  = intent_result.get("intent",{})
        entities     = intent_result.get("entities",{})
        label        = intent_info.get("label","")
        display_name = intent_info.get("display_name","ทั่วไป")
        confidence   = intent_info.get("confidence",0.0)

        # Context — label top chunk สำหรับ curriculum
        if retrieval_results:
            if label == "curriculum_info":
                gen = entities.get("generation","")
                plan = entities.get("plan","")
                yr  = entities.get("year","")
                sem = entities.get("semester","")
                sem_label = "ฤดูร้อน" if sem=="summer" else f"เทอม {sem}"
                top_label = f"[ข้อมูลที่ตรงกับคำถามมากที่สุด — อ่านข้อนี้ก่อน: ปี {yr} {sem_label} รุ่น {gen} แผน{plan}]"
                parts = [f"[1] {top_label}\n{retrieval_results[0]['text']}"]
                parts += [f"[{i}] {r['text']}" for i,r in enumerate(retrieval_results[1:],2)]
                context_text = "\n\n".join(parts)
            else:
                context_text = "\n\n".join(f"[{i}] {r['text']}"
                                            for i,r in enumerate(retrieval_results,1))
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
2.1 [สำคัญมาก] หาก Intent เป็นแผนการเรียน ให้ทำตามขั้นตอนนี้:
    ก. อ่าน Context [1] ก่อนเสมอ เพราะมีป้ายกำกับว่า "[ข้อมูลที่ตรงกับคำถามมากที่สุด]"
    ข. มองหา Header "#### รุ่น Z (แผนW)" ที่ตรงกับคำถาม แล้วดึงรายวิชาและหน่วยกิตจาก Block นั้น
    ค. ห้ามตอบว่า "ไม่พบข้อมูล" ถ้า Context [1] มีหัวข้อที่ตรงอยู่
    ง. [กำชับ] ข้อมูลที่ถามมีอยู่ใน Context [1] แน่นอน จงอ่านทุกบรรทัดก่อนตอบ
3. ถ้า Context ไม่มีข้อมูล ให้บอกตรงๆ อย่างสุภาพ
3.1 ถ้า Context มีรหัสวิชา (เช่น AIE455 หรือ AIE 455) ให้สรุปชื่อและคำอธิบายทันที
3.2 หากมีชื่อบุคคลหรือสถานที่ตรงกับคำถาม ให้ตอบตามนั้นทันที
4. Emotion: "Normal"=ทักทาย, "Talking"=ให้ข้อมูล, "Curious"=ไม่พบข้อมูล
5. data_type: "fact"=ดึงจาก Context, "logic"=วิเคราะห์เอง/ไม่พบ
6. speech_text: ห้ามมี * # | bullet ตัวย่อที่อ่านไม่ออก

Return ONLY raw JSON ไม่มี markdown:
{{
    "display_text": "คำตอบแสดงบนหน้าจอ (ภาษาไทย)",
    "speech_text": "คำตอบสำหรับ TTS (ภาษาไทย ไม่มีสัญลักษณ์)",
    "emotion": "Normal/Talking/Curious",
    "response_metadata": {{
        "data_type": "fact/logic",
        "confidence_score": 0.0
    }}
}}"""

        for model in self.models_to_try:
            for attempt in range(2):   # retry 1 ครั้งต่อ model กรณี JSON fail
                try:
                    result_json = self._call_api(model, prompt)
                    candidates  = result_json.get("candidates",[])
                    if not candidates:
                        print(f"[LLM] {model}: no candidates")
                        break
                    text_response = candidates[0]["content"]["parts"][0]["text"]
                    parsed = self._parse_json_response(text_response)
                    if parsed:
                        return parsed
                    print(f"[LLM] {model}: ไม่พบ JSON (attempt {attempt+1})")
                    if attempt == 0:
                        time.sleep(1)  # รอสั้นๆ ก่อน retry
                except Exception as e:
                    err = str(e)
                    if "429" in err:
                        m = re.search(r"retry in (\d+)", err)
                        wait = int(m.group(1))+2 if m else self.retry_wait
                        print(f"[LLM] {model}: quota → รอ {wait}s")
                        time.sleep(wait)
                    elif "403" in err:
                        print(f"[LLM] {model}: PERMISSION_DENIED → ข้าม")
                    else:
                        print(f"[LLM Warning] {model} failed: {e}")
                    break  # ข้าม model นี้ทันที

        print("[LLM Error] ทุก model ล้มเหลว")
        return None