import re
import json
import torch
import pickle
import os

from pythainlp.tokenize import word_tokenize
from pythainlp.util import normalize
from transformers import AutoTokenizer, AutoModelForSequenceClassification

DEFAULT_MODEL_PATH = "/Users/aoyrzz/Desktop/AIDA-chatbot/backend/ai_core/intent_model"

DISPLAY_NAMES = {
    "admission_info":  "[หมวดหมู่: ค่าเทอมและการเงิน]",
    "curriculum_info": "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร]",
    "degreeplan2565":  "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี2565]",
    "degreeplan2566":  "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี2566]",
    "degreeplan2567":  "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี2567]",
    "degreeplan2568":  "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี2568]",
    "staff_info":      "[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]",
    "small_talk":      "[หมวดหมู่: พูดคุยทั่วไป]",
    "toxic":           "[หมวดหมู่: คำไม่สุภาพ]",
    "report_issue":    "[หมวดหมู่: แจ้งปัญหาการใช้งาน]",
    "greeting":        "[หมวดหมู่: ทักทาย]",
    # career_info → ยังคงใช้ tag เดิมไว้ก่อน
    # ให้แก๊งเพิ่ม chunks เรื่องอาชีพเข้า KB พร้อม tag นี้
    "career_info":     "[หมวดหมู่: ข้อมูลสาขาวิชา]",
    "compare_options": "[หมวดหมู่: เปรียบเทียบข้อมูล/ทางเลือก]",
    "out_of_scope":    "[หมวดหมู่: นอกเหนือขอบเขต]",
    "course_desc":     "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]",
    "coop_intern":     "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]",
    "mou_company":     "[หมวดหมู่: เครือข่ายบริษัท/MOU]",
}


class ThaiIntentClassifier:
    def __init__(self, model_path=DEFAULT_MODEL_PATH):
        self.model_path  = model_path
        self.tokenizer   = None
        self.model       = None
        self.label_encoder = None
        self.is_loaded   = False

    def load(self):
        print(f"กำลังโหลดสมองส่วนแยกแยะ Intent จาก: {self.model_path} ...")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"[ERROR] ไม่พบโฟลเดอร์โมเดลที่: {self.model_path}")
        try:
            self.tokenizer   = AutoTokenizer.from_pretrained(self.model_path)
            self.model       = AutoModelForSequenceClassification.from_pretrained(self.model_path)
            with open(os.path.join(self.model_path, "label_encoder.pkl"), "rb") as f:
                self.label_encoder = pickle.load(f)
            self.is_loaded = True
            print("[OK] โหลดโมเดลสำเร็จ! พร้อมทำงาน\n")
        except Exception as e:
            raise RuntimeError(f"[ERROR] เกิดข้อผิดพลาดในการโหลดโมเดล: {e}")

    def _extract_entities(self, text: str) -> dict:
        year_match      = re.search(r"ปี\s*([1-4])", text)
        year            = year_match.group(1) if year_match else ""
        curr_year_match = re.search(r"(256[5-9]|6[5-9])", text)
        curriculum_year = curr_year_match.group(1) if curr_year_match else ""
        if len(curriculum_year) == 2:
            curriculum_year = "25" + curriculum_year
        semester_match = re.search(r"เทอม\s*(\d)", text)
        semester       = semester_match.group(1) if semester_match else ""
        course_match   = re.search(r"([a-zA-Z]{3}\d{3})", text)
        course_code    = course_match.group(1).upper() if course_match else ""

        # ── รุ่น: 1/1, 1/2, 2 ──────────────────────────────────────────────
        gen = ""
        text_lower = text.lower()
        if re.search(r"รุ่น\s*1\s*/\s*1|รุ่นหนึ่งทับหนึ่ง|gen\s*1[/_]1", text_lower):
            gen = "1/1"
        elif re.search(r"รุ่น\s*1\s*/\s*2|รุ่นหนึ่งทับสอง|gen\s*1[/_]2", text_lower):
            gen = "1/2"
        elif re.search(r"รุ่น\s*2\b|รุ่นสอง\b|gen\s*2\b", text_lower):
            gen = "2"

        # ── แผน: ปกติ, สหกิจ ───────────────────────────────────────────────
        plan = ""
        if any(w in text_lower for w in ["สหกิจ", "coop", "co-op"]):
            plan = "สหกิจ"
        elif any(w in text_lower for w in ["ปกติ", "normal", "regular"]):
            plan = "ปกติ"

        keyword_pool   = ["จ่าย", "กี่บาท", "ค่าเทอม", "หน่วยกิต", "ราคา", "เท่าไหร่",
                          "เรียน", "ฝึกงาน", "จบ", "วิชา", "เกี่ยวกับอะไร",
                          "แผนการเรียน", "โครงสร้างหลักสูตร", "degree plan"]
        found_keywords = [kw for kw in keyword_pool if kw in text_lower]
        return {
            "year":            year,
            "curriculum_year": curriculum_year,
            "semester":        semester,
            "course_code":     course_code,
            "generation":      gen,    # รุ่น 1/1, 1/2, 2
            "plan":            plan,   # แผนปกติ / แผนสหกิจ
            "keywords":        found_keywords,
        }

    def _format_output(self, original_text: str, raw_intent: str,
                       confidence: float, is_fallback: bool = False) -> dict:
        entities_data = self._extract_entities(original_text)
        display_name  = DISPLAY_NAMES.get(raw_intent, "หมวดหมู่ทั่วไป")
        target_years  = ["2565", "2566", "2567", "2568"]
        if raw_intent == "curriculum_info" and entities_data.get("curriculum_year") in target_years:
            display_name = f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี{entities_data['curriculum_year']}]"
        return {
            "original_query": original_text,
            "intent": {
                "label":        str(raw_intent),
                "confidence":   round(confidence, 4),
                "display_name": display_name
            },
            "entities":        entities_data,
            "processing_meta": {"model": "WangchanBERTa-AIE-FineTuned", "is_fallback": is_fallback}
        }

    def predict(self, text: str) -> dict:
        if not self.is_loaded:
            raise RuntimeError("[ERROR] ยังไม่ได้ load model — เรียก .load() ก่อน")

        clean_text   = normalize(text)
        clean_text   = re.sub(r'([ก-๙])\1{2,}', r'\1', clean_text)
        tokens       = word_tokenize(clean_text, engine="newmm")
        tokens_lower = [t.lower() for t in tokens]   # ใช้ token list ตลอด

        # ════════════════════════════════════
        # ด่าน 2: Rule-based — ดักคำสำคัญ
        # ════════════════════════════════════

        # 1. Toxic
        toxic_keywords = {"โง่","สัส","เหี้ย","ควาย","กาก","ปัญญาอ่อน","สถุน",
                          "ควย","มึง","กู","กุ","เอ๋อ","เหว๋อ","ตอแหล","หี","แตด"}
        if any(w in toxic_keywords for w in tokens):
            return self._format_output(text, "toxic", 1.0, is_fallback=True)

        # 2. Report issue
        issue_keywords = ["พัง","ล่ม","เข้าไม่ได้","ล็อกอิน","รหัสผ่าน","ไวไฟ","เน็ต"]
        if any(w in clean_text for w in issue_keywords):
            return self._format_output(text, "report_issue", 1.0, is_fallback=True)

        # 3. Greeting  ← FIX Bug 1: token check แทน substring
        greetings = ["สวัสดี","หวัดดี","ทัก","ฮัลโหล","มอนิ่ง",
                     "ดีจ้า","ดีครับ","ดีค่ะ","hey","hi"]
        if any(w in tokens_lower for w in greetings):
            return self._format_output(text, "greeting", 1.0, is_fallback=True)

        # 4. Bot name questions → small_talk
        bot_name_questions = ["ชื่ออะไร","เธอชื่ออะไร","ตัวเองชื่ออะไร",
                               "บอทชื่ออะไร","น้องชื่ออะไร","ชื่อไร"]
        if clean_text in bot_name_questions:
            return self._format_output(text, "small_talk", 1.0, is_fallback=True)

        # 5. Career
        career_keywords = ["เงินเดือน","ทำงาน","จบไป","อาชีพ","ตลาดงาน","ตกงาน"]
        if any(w in clean_text for w in career_keywords):
            return self._format_output(text, "career_info", 1.0, is_fallback=True)

        # 6. Admission
        admission_keywords = ["ค่าเทอม","กู้","ทุน","รับสมัคร",
                               "สัมภาษณ์","จ่ายเงิน","ผ่อนผัน"]
        if any(w in clean_text for w in admission_keywords):
            return self._format_output(text, "admission_info", 1.0, is_fallback=True)

        # 7. Coop  ← FIX Bug 2: ขึ้นก่อน mou
        coop_keywords = ["สหกิจ","ฝึกงาน","co-op","coop","intern","สถานที่ฝึกงาน"]
        if any(w in clean_text.lower() for w in coop_keywords):
            return self._format_output(text, "coop_intern", 1.0, is_fallback=True)

        # 8. MOU company
        mou_keywords = ["บริษัท","MANGO CONSULTANT","Odd-e","Softnix","DNA ROBOTICS",
                        "IIS AUTOMATION","Huawei","EPE Packaging","BOTNOI","UiPath",
                        "การประปาส่วนภูมิภาค","RV Connex","สภาเภสัชกรรม","A.I Technology"]
        if any(w in clean_text for w in mou_keywords):
            return self._format_output(text, "mou_company", 1.0, is_fallback=True)

        # 9. Curriculum (strong signal)
        curriculum_strong = ["แผนการเรียน","โครงสร้างหลักสูตร","degree plan","ดีกรีแพลน","degreeplan"]
        if any(w in clean_text.lower() for w in curriculum_strong):
            return self._format_output(text, "curriculum_info", 1.0, is_fallback=True)

        # 10. Course description (รหัสวิชา หรือ keyword)
        course_desc_keywords = ["เรียนเกี่ยวกับอะไร","เรียนอะไร","คือวิชาอะไร","สอนอะไร","สอนเกี่ยวกับอะไร"]
        course_match = re.search(r"([a-zA-Z]{3}\d{3})", clean_text)
        if course_match or any(w in clean_text for w in course_desc_keywords):
            return self._format_output(text, "course_desc", 1.0, is_fallback=True)

        # 11. Staff info  ← FIX 3: เพิ่ม "ดร." และ "ดอกเตอร์"
        staff_keywords = ["อาจารย์","อจ","ผู้สอน","ดร.","ดอกเตอร์","รศ.","ผศ.","สอน"]
        if any(w in clean_text for w in staff_keywords):
            return self._format_output(text, "staff_info", 1.0, is_fallback=True)

        # 12. Curriculum (weak signal)
        curriculum_weak = ["เรียนยาก","หน่วยกิต","วิชา"]
        if any(w in clean_text for w in curriculum_weak):
            return self._format_output(text, "curriculum_info", 1.0, is_fallback=True)

        # 13. "ชื่อ...อะไร" ที่ไม่ใช่ถามบุคลากร → small_talk
        if "ชื่อ" in clean_text and "อะไร" in clean_text:
            ignore = ["อาจารย์","จารย์","คณะ","สาขา","มหาลัย","วิชา","คณบดี","ผอ","ผู้อำนวยการ"]
            if not any(w in clean_text for w in ignore):
                return self._format_output(text, "small_talk", 1.0, is_fallback=True)

        # 14. Closing → small_talk
        closing = ["ขอบคุณ","แต๊งกิ้ว","บ๊ายบาย","บาย","bye","ขอบใจ"]
        if any(w in clean_text.lower() for w in closing):
            return self._format_output(text, "small_talk", 1.0, is_fallback=True)

        # ════════════════════════════════════
        # ด่าน 3: WangchanBERTa Transformer
        # ════════════════════════════════════
        inputs = self.tokenizer(clean_text, return_tensors="pt",
                                truncation=True, padding=True, max_length=128)
        with torch.no_grad():
            outputs = self.model(**inputs)

        probs      = torch.softmax(outputs.logits, dim=1)[0]
        pred_id    = torch.argmax(outputs.logits, dim=1).item()
        raw_intent = self.label_encoder.inverse_transform([pred_id])[0]
        confidence = float(probs[pred_id].item())

        # ด่าน 4: Safety zone
        if confidence < 0.50:
            return self._format_output(text, "out_of_scope", confidence, is_fallback=True)

        return self._format_output(text, raw_intent, confidence, is_fallback=False)

    def predict_as_json(self, text: str) -> str:
        return json.dumps(self.predict(text), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    clf = ThaiIntentClassifier()
    clf.load()
    tests = [
        "สวัสดีครับ",
        "ดร. ใครสอนวิชา Machine Learning",   # Bug1 fix test
        "สหกิจมีบริษัทอะไรบ้าง",              # Bug2 fix test
        "ค่าเทอมปี 1 เท่าไหร่",
        "จบไปทำงานอะไรได้บ้าง",
        "Huawei เป็น MOU กับสาขาไหม",
        "ระบบเน็ตล่ม เข้าไม่ได้เลย",
        "ใครชนะบอลโลก 2026",
    ]
    for q in tests:
        r = clf.predict(q)
        print(f"{q[:45]:<46} → {r['intent']['label']} ({r['intent']['confidence']:.2f})")