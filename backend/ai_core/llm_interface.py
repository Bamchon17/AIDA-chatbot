import os, re, json, time, requests
from dotenv import load_dotenv
load_dotenv()


class LLMInterface:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("[ERROR] GEMINI_API_KEY not found in .env file")
        self.models_to_try = [
            "gemini-2.5-flash",   # หลัก: เร็ว
            "gemini-2.5-pro",     # fallback: แม่นยำกว่า
        ]
        self.retry_wait = 5

    def _call_api(self, model_name: str, prompt: str) -> dict:
        clean = model_name.replace("models/","")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{clean}:generateContent?key={self.api_key}")
        
        # 🚨 ปรับแก้ Payload ตรงนี้ครับ
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.95,
                "maxOutputTokens": 8192
            }
        }
        
        r = requests.post(url, 
                          headers={"Content-Type":"application/json"},
                          json=payload, 
                          timeout=30)
        if r.status_code == 200:
            return r.json()
        raise Exception(f"HTTP {r.status_code}: {r.text}")

    def _extract_text_from_response(self, result_json: dict) -> str | None:
        """ดึง text จาก Gemini response — รองรับ candidates[0].content.parts หลาย parts"""
        candidates = result_json.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        # รวมทุก part ที่เป็น text
        text = " ".join(p.get("text", "") for p in parts if "text" in p).strip()
        return text if text else None

    def _parse_json_response(self, text: str) -> dict | None:
        """
        Parse JSON จาก LLM response — ultra-robust version
        รองรับ: markdown fence, BOM, control chars, partial JSON
        """
        if not text:
            return None

        # 1. ลบ BOM และ control characters ที่ไม่ใช่ whitespace
        text = text.strip()
        text = re.sub(r'^\ufeff', '', text)                      # BOM
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)  # control chars

        # 2. ลบ markdown fence (รองรับหลายรูปแบบ)
        #    ```json ... ``` หรือ ``` ... ``` หรือ `{...}`
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        # 3. ลอง parse ตรง
        try:
            return json.loads(text)
        except Exception:
            pass

        # 4. Brace matching — หา JSON object ที่สมบูรณ์ที่สุด
        start = text.find("{")
        if start != -1:
            depth = 0
            in_string = False
            escape_next = False
            for i, ch in enumerate(text[start:], start):
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\" and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                if not in_string:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                    if depth == 0:
                        candidate = text[start:i + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # ลอง fix common escape issues แล้ว parse อีกครั้ง
                            fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', candidate)
                            try:
                                return json.loads(fixed)
                            except Exception:
                                break

        # 5. Regex greedy fallback
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        # 6. แจ้งเตือนพร้อม preview
        preview = text[:200].replace('\n', ' ')
        print(f"[LLM] ⚠ parse_json ล้มเหลวทั้งหมด | preview: {preview}")
        return None

    def _build_entity_context(self, entities: dict) -> str:
        parts = []
        if entities.get("curriculum_year"): parts.append(f"ปีหลักสูตร: {entities['curriculum_year']}")
        if entities.get("year"):            parts.append(f"ชั้นปีที่: {entities['year']}")
        if entities.get("semester"):
            sem = entities["semester"]
            parts.append(f"เทอม: {'ฤดูร้อน (Summer)' if sem == 'summer' else sem}")
        if entities.get("generation"):      parts.append(f"รุ่น: {entities['generation']}")
        if entities.get("plan"):            parts.append(f"แผน: {entities['plan']}")
        if entities.get("course_code"):     parts.append(f"รหัสวิชา: {entities['course_code']}")
        if entities.get("keywords"):        parts.append(f"คำสำคัญ: {', '.join(entities['keywords'])}")
        if entities.get("generation") and entities.get("plan"):
            gen  = entities["generation"]
            plan = entities["plan"]
            sem  = entities.get("semester", "")
            sem_text = " ภาคการศึกษาฤดูร้อน" if sem == "summer" else (f" ภาคการศึกษาที่ {sem}" if sem else "")
            parts.append(f"[ค้นหาใน Context: หัวข้อ '#### รุ่น {gen} (แผน{plan})'{sem_text}]")
        return "  ".join(parts) if parts else "ไม่มีข้อมูลเพิ่มเติม"

    def generate_response(self, query: str, retrieval_results: list,
                          intent_result: dict, sentiment: str = "normal") -> dict | None:
        intent_info  = intent_result.get("intent",{})
        entities     = intent_result.get("entities",{})
        label        = intent_info.get("label","")
        display_name = intent_info.get("display_name","ทั่วไป")
        confidence   = intent_info.get("confidence",0.0)

        # โหมดที่ 1: คุยเล่นและทักทาย (Small Talk & Greeting)
        if label in ["greeting", "small_talk"]:
            prompt = f"""
            คุณคือ "AIDA (ไอด้า)" เป็นผู้ช่วย AI สาวน้อยประจำสาขาวิศวกรรมปัญญาประดิษฐ์และวิทยาการข้อมูล มหาวิทยาลัยกรุงเทพ
            ผู้ใช้พิมพ์มาว่า: "{query}"
            
            คำสั่ง:
            1. ตอบกลับผู้ใช้อย่างเป็นธรรมชาติ เป็นมิตร สดใส และมีหางเสียง (ค่ะ/คะ)
            2. สามารถหยอกล้อพูดคุยตามบริบทได้ **แต่ห้ามเสนอตัวช่วยเหลือ ค้นหาข้อมูล หรือให้คำแนะนำในสิ่งที่ไม่เกี่ยวกับสาขาวิชา/มหาวิทยาลัย (เช่น ห้ามแนะนำที่เที่ยว ห้ามเล่านิทาน ห้ามเขียนโค้ด)**
            3. หากผู้ใช้คุยเรื่องนอกขอบเขต ให้ตอบรับสั้นๆ น่ารักๆ แล้วชวนคุยดึงกลับมาที่เรื่องเรียน สาขาวิชา หรือถามว่ามีอะไรให้ช่วยเกี่ยวกับคณะไหมคะ
            4. ห้ามพูดว่า "ไม่พบข้อมูลในฐานข้อมูล" เด็ดขาด
            5. ตอบกลับมาเป็น JSON Format เท่านั้น
            
            ตัวอย่าง JSON:
            {{
                "display_text": "สวัสดีค่า! วันนี้มีอะไรให้ไอด้าช่วยไหมคะ 🥰",
                "speech_text": "สวัสดีค่า วันนี้มีอะไรให้ไอด้าช่วยไหมคะ",
                "emotion": "Happy",
                "response_metadata": {{"data_type": "logic", "confidence_score": 1.0}}
            }}
            """
            
        # โหมดที่ 2: ตอบคำถามเชิงวิชาการ (Prompt ของคุณ + ห้ามสวัสดี)
        else:
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

            # Prompt เดิม 100%
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
4. Emotion: ให้เลือกใช้ตามเงื่อนไขดังนี้เท่านั้น
   - "Curious" = บังคับใช้เมื่อ Context คือ "ไม่พบข้อมูลในระบบฐานข้อมูล", ข้อมูลไม่เพียงพอ, หรือเป็นคำถามนอกเรื่อง (Out of scope)
   - "Talking" = เมื่อสามารถให้คำตอบจาก Context ได้ตามปกติ
5. data_type: "fact"=ดึงจาก Context, "logic"=วิเคราะห์เอง/ไม่พบ
6. speech_text: ห้ามมี * # | bullet ตัวย่อที่อ่านไม่ออก เช่น "ก." "ข." ให้เขียนเต็ม
7. [สำคัญมาก] ห้ามเริ่มต้นประโยคด้วยคำว่า "สวัสดี" เด็ดขาด ให้พุ่งเป้าไปที่การอธิบายข้อมูลหรือตอบคำถามทันที เพื่อความกระชับ

CRITICAL: ตอบเป็น JSON object เท่านั้น ห้ามมี markdown, ห้ามมีข้อความนอก JSON เด็ดขาด
ตัวอย่าง output ที่ถูกต้อง:
{{"display_text":"...","speech_text":"...","emotion":"Talking","response_metadata":{{"data_type":"fact","confidence_score":0.9}}}}

JSON Schema:
{{
    "display_text": "คำตอบแสดงบนหน้าจอ (ภาษาไทย)",
    "speech_text": "คำตอบสำหรับ TTS (ภาษาไทย ไม่มีสัญลักษณ์)",
    "emotion": "Talking|Curious",
    "response_metadata": {{
        "data_type": "fact|logic",
        "confidence_score": 0.0
    }}
}}"""

        for model in self.models_to_try:
            for attempt in range(2):
                try:
                    result_json   = self._call_api(model, prompt)
                    text_response = self._extract_text_from_response(result_json)

                    if not text_response:
                        print(f"[LLM] {model}: no text in response (attempt {attempt + 1})")
                        # log finish_reason ถ้ามี
                        try:
                            reason = result_json["candidates"][0].get("finishReason", "?")
                            print(f"[LLM] {model}: finishReason={reason}")
                        except Exception:
                            pass
                        if attempt == 0:
                            time.sleep(1)
                        continue

                    parsed = self._parse_json_response(text_response)
                    if parsed:
                        # Validate fields ที่จำเป็น
                        if all(k in parsed for k in ("display_text", "speech_text", "emotion")):
                            return parsed
                        print(f"[LLM] {model}: JSON ไม่ครบ fields (attempt {attempt + 1})")
                    else:
                        print(f"[LLM] {model}: ไม่พบ JSON (attempt {attempt + 1})")

                    if attempt == 0:
                        time.sleep(1)

                except Exception as e:
                    err = str(e)
                    if "429" in err:
                        m = re.search(r"retry[_ ]in[_ ](\d+)", err)
                        wait = int(m.group(1)) + 2 if m else self.retry_wait
                        print(f"[LLM] {model}: quota → รอ {wait}s")
                        time.sleep(wait)
                        break
                    elif "403" in err:
                        print(f"[LLM] {model}: PERMISSION_DENIED → ข้าม")
                        break
                    elif "503" in err or "502" in err:
                        print(f"[LLM] {model}: service unavailable → รอ 3s")
                        time.sleep(3)
                        break
                    else:
                        print(f"[LLM Warning] {model} attempt {attempt + 1} failed: {e}")
                        if attempt == 0:
                            time.sleep(1)

        print("[LLM Error] ทุก model ล้มเหลว")
        return None
