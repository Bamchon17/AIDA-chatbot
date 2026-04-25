import re
import json
import torch
import pickle
import os

from pythainlp.tokenize import word_tokenize
from pythainlp.util import normalize
from transformers import AutoTokenizer, AutoModelForSequenceClassification

DEFAULT_MODEL_PATH = "./ai_core/intent_model"

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
    "career_info":     "[หมวดหมู่: ข้อมูลสาขาวิชา]",
    "compare_options": "[หมวดหมู่: เปรียบเทียบข้อมูล/ทางเลือก]",
    "out_of_scope":    "[หมวดหมู่: นอกเหนือขอบเขต]",
    "course_desc":     "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]",
    "coop_intern":     "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]",
    "mou_company":     "[หมวดหมู่: เครือข่ายบริษัท/MOU]",
    "general_info":    "[หมวดหมู่: ข้อมูลทั่วไป]",
}

# ลบ COHORT_MAPPER ออกไปแล้ว เพื่อให้ app.py เป็นคนจัดการแทน


class ThaiIntentClassifier:
    def __init__(self, model_path=DEFAULT_MODEL_PATH):
        self.model_path    = model_path
        self.tokenizer     = None
        self.model         = None
        self.label_encoder = None
        self.is_loaded     = False

    def load(self):
        print(f"กำลังโหลดสมองส่วนแยกแยะ Intent จาก: {self.model_path} ...")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"[ERROR] ไม่พบโฟลเดอร์โมเดลที่: {self.model_path}")
        try:
            self.tokenizer     = AutoTokenizer.from_pretrained(self.model_path)
            self.model         = AutoModelForSequenceClassification.from_pretrained(self.model_path)
            with open(os.path.join(self.model_path, "label_encoder.pkl"), "rb") as f:
                self.label_encoder = pickle.load(f)
            self.is_loaded = True
            print("[OK] โหลดโมเดลสำเร็จ! พร้อมทำงาน\n")
        except Exception as e:
            raise RuntimeError(f"[ERROR] เกิดข้อผิดพลาดในการโหลดโมเดล: {e}")

    def _extract_entities(self, text: str) -> dict:
        # ---- หลักสูตรปี (2565-2568 หรือ 65-68) ----
        curr_year_match = re.search(r"(256[5-9]|2570|6[5-9])", text)
        curriculum_year = curr_year_match.group(1) if curr_year_match else ""
        if curriculum_year and len(curriculum_year) == 2:
            curriculum_year = "25" + curriculum_year

        # ---- ชั้นปี (1-6) — หลีกเลี่ยงชนกับรหัสนักศึกษา ----
        year_match = re.search(r"ปี\s*([1-6])(?!\d)", text)
        year       = year_match.group(1) if year_match else ""

        # ---- เทอม ----
        semester_match = re.search(r"เทอม\s*([1-3])\b", text)
        semester       = semester_match.group(1) if semester_match else ""
        if not semester and re.search(r"ซัมเมอร์|summer|ฤดูร้อน|ภาคฤดูร้อน", text.lower()):
            semester = "summer"

        # ---- รหัสวิชา ----
        course_match = re.search(r"([a-zA-Z]{2,4})\s*(\d{3})", text)
        course_code  = (course_match.group(1) + course_match.group(2)).upper() if course_match else ""

        # ---- รุ่น: รองรับแค่รูปแบบ "รุ่น 1/1", "รุ่น 3" (ลบการดัก prefix 65 ออกแล้ว) ----
        gen = ""
        text_lower = text.lower()

        # รูปแบบ "รุ่น X/Y"
        m_gen_slash = re.search(r"รุ่น\s*(\d)\s*/\s*(\d)", text_lower)
        if m_gen_slash:
            gen = f"{m_gen_slash.group(1)}/{m_gen_slash.group(2)}"
        else:
            # รูปแบบ "รุ่น N" (ตัวเลข)
            m_gen_num = re.search(r"รุ่น\s*([1-7])\b", text_lower)
            if m_gen_num:
                gen = m_gen_num.group(1)
            # เอาส่วนที่แปลรหัส 63-69 เป็นรุ่นออกไปแล้ว

        # ---- แผน ----
        plan = ""
        if any(w in text_lower for w in ["สหกิจ", "coop", "co-op"]):
            plan = "สหกิจ"
        elif any(w in text_lower for w in ["ปกติ", "normal", "regular"]):
            plan = "ปกติ"

        # ---- Keywords ----
        keyword_pool   = ["จ่าย", "กี่บาท", "ค่าเทอม", "หน่วยกิต", "ราคา", "เท่าไหร่",
                          "เรียน", "ฝึกงาน", "จบ", "วิชา", "เกี่ยวกับอะไร",
                          "แผนการเรียน", "โครงสร้างหลักสูตร", "degree plan"]
        found_keywords = [kw for kw in keyword_pool if kw in text_lower]

        return {
            "year":            year,
            "curriculum_year": curriculum_year,
            "semester":        semester,
            "course_code":     course_code,
            "generation":      gen,
            "plan":            plan,
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
        tokens_lower = [t.lower() for t in tokens]
        text_lower   = clean_text.lower()

        # =========================================================
        # Rule-based: เรียงลำดับจาก specific → general
        # =========================================================

        # 1. Toxic (สูงสุด)
        toxic_keywords = {"โง่","สัส","เหี้ย","ควาย","กาก","ปัญญาอ่อน","สถุน",
                          "ควย","มึง","กู","กุ","เอ๋อ","เหว๋อ","ตอแหล","หี","แตด"}
        if any(w in toxic_keywords for w in tokens):
            return self._format_output(text, "toxic", 1.0, is_fallback=True)

        # 2. Report issue
        issue_keywords = ["พัง","ล่ม","เข้าไม่ได้","ล็อกอิน","รหัสผ่าน","ไวไฟ","เน็ต","ระบบขัดข้อง"]
        if any(w in clean_text for w in issue_keywords):
            return self._format_output(text, "report_issue", 1.0, is_fallback=True)

        # 3. Greeting
        greetings = ["สวัสดี","หวัดดี","ฮัลโหล","มอนิ่ง","ดีจ้า","ดีครับ","ดีค่ะ","hey","hi","hello","ทักทาย"]
        if any(w in tokens_lower for w in greetings):
            return self._format_output(text, "greeting", 1.0, is_fallback=True)

        # 4. Bot name → small_talk (ป้องกัน match แบบ full-text เท่านั้น)
        bot_name_questions = ["ชื่ออะไร","เธอชื่ออะไร","ตัวเองชื่ออะไร","บอทชื่ออะไร","น้องชื่ออะไร","ชื่อไร"]
        if clean_text.strip() in bot_name_questions:
            return self._format_output(text, "small_talk", 1.0, is_fallback=True)

        # 4b. Course content keywords
        course_content_kw = ["mlops","ci/cd","machine learning operation","สอนเรื่อง",
                              "วิชาอะไรที่สอน","วิชาที่สอน","วิชาเกี่ยวกับ","วิชาที่เกี่ยวกับ"]
        if any(w in text_lower for w in course_content_kw):
            return self._format_output(text, "course_desc", 1.0, is_fallback=True)

        # 5. Career info (รายละเอียดสาขา/ข้อมูลสาขา)
        major_keywords = [
            "รายละเอียดสาขา", "ข้อมูลสาขา", "สาขาวิศวกรรม", "สาขา ai",
            "สาขา data", "วิศวกรรมปัญญาประดิษฐ์", "วิทยาการข้อมูล",
            "ai and data science", "เรียนสาขานี้", "สาขานี้เรียนอะไร",
            "สาขานี้เป็นยังไง", "สาขานี้ดีไหม", "สาขานี้น่าเรียนไหม",
            "เกี่ยวกับสาขา", "ข้อมูลเกี่ยวกับสาขา", "ภาพรวมสาขา",
            "หลักสูตรสาขา", "จุดเด่นของสาขา"
        ]
        if any(w in text_lower for w in major_keywords):
            return self._format_output(text, "career_info", 1.0, is_fallback=True)

        # 5b. Facility/Lab → career_info
        facility_keywords = [
            "robot studio","robotstudio","ai lab","ai innovation","bu croccs","croccs",
            "ห้องปฏิบัติการ","ห้องแล็บ","ห้องlab","ห้อง lab","lab ที่สาขา","แล็บ"
        ]
        if any(w in text_lower for w in facility_keywords):
            return self._format_output(text, "career_info", 1.0, is_fallback=True)

        # 6. Career (อาชีพ/ตลาดงาน — ชัดเจนว่าเรื่องงาน)
        career_keywords = [
            "เงินเดือน","ทำงานอะไรได้","จบไปทำงาน","อาชีพ","ตลาดงาน","ตกงาน",
            "หางาน","งานที่ทำได้","ทำงานได้ที่ไหน","เส้นทางอาชีพ","career path",
            "job","ตำแหน่งงาน","ทักษะที่ต้องการ","demand ในตลาด"
        ]
        if any(w in text_lower for w in career_keywords):
            return self._format_output(text, "career_info", 1.0, is_fallback=True)

        # 7. Admission / การเงิน
        admission_keywords = ["ค่าเทอม","กู้","ทุน","รับสมัคร","สัมภาษณ์","จ่ายเงิน","ผ่อนผัน","ค่าลงทะเบียน"]
        if any(w in clean_text for w in admission_keywords):
            return self._format_output(text, "admission_info", 1.0, is_fallback=True)

        # 7b. General info (มหาวิทยาลัย/สถานที่/การเดินทาง)
        general_keywords = [
            "สมัครเรียน","สมัครเข้า","เอกสารสมัคร","คุณสมบัติผู้สมัคร",
            "เทียบโอน","ปวส","ปวช","ม.กรุงเทพ","มหาวิทยาลัยกรุงเทพ",
            "ที่ตั้งคณะ","ตึก b4","b4 ชั้น","ติดต่อคณะ","เดินทางมา",
            "รถเมล์","รถตู้","bts","mrt","สายสี","คณะมีกี่สาขา",
            "สาขาในคณะ","สาขาวิชาที่เปิด"
        ]
        if any(w in text_lower for w in general_keywords):
            return self._format_output(text, "general_info", 1.0, is_fallback=True)

        # 8. Coop/Intern
        coop_keywords = ["สหกิจ","ฝึกงาน","co-op","coop","intern","สถานที่ฝึกงาน","ออกสหกิจ"]
        if any(w in text_lower for w in coop_keywords):
            return self._format_output(text, "coop_intern", 1.0, is_fallback=True)

        # 9. MOU company
        mou_keywords = [
            "บริษัท","mango consultant","odd-e","softnix","dna robotics",
            "iis automation","huawei","epe packaging","botnoi","uipath",
            "การประปาส่วนภูมิภาค","rv connex","สภาเภสัชกรรม","a.i technology",
            "พาร์ทเนอร์","partner","mou","เอ็มโอยู"
        ]
        if any(w in text_lower for w in mou_keywords):
            return self._format_output(text, "mou_company", 1.0, is_fallback=True)

        # 10. Curriculum (strong keywords)
        curriculum_strong = [
            "แผนการเรียน","โครงสร้างหลักสูตร","degree plan","ดีกรีแพลน",
            "degreeplan","แผนปี","ตารางเรียน","วิชาในแผน"
        ]
        if any(w in text_lower for w in curriculum_strong):
            return self._format_output(text, "curriculum_info", 1.0, is_fallback=True)

        # 10b. Short reply: 🚨 ดักรหัส 63-69 และ ปี 1-6 ตรงนี้!
        _ents_quick = self._extract_entities(clean_text)
        _is_plan_reply = (
            len(clean_text.strip()) <= 20
            and (
                _ents_quick.get("plan") 
                or _ents_quick.get("generation") 
                or _ents_quick.get("year") 
                or bool(re.search(r"\b(6[3-9])\b", clean_text))
            )
        )
        if _is_plan_reply:
            return self._format_output(text, "curriculum_info", 1.0, is_fallback=True)

        # 10c. มีปี + เทอมพร้อมกัน → curriculum
        _has_year_AND_sem = (
            bool(re.search(r"ปี\s*[1-6]", clean_text))
            and bool(re.search(r"เทอม\s*[1-3]", clean_text))
        )
        if _has_year_AND_sem:
            return self._format_output(text, "curriculum_info", 1.0, is_fallback=True)

        # 11. Course description (รหัสวิชา หรือ keyword เรียนอะไร — ไม่มีปี+เทอม)
        _has_year_or_sem = bool(re.search(r"ปี\s*[1-6]|เทอม\s*[1-3]", clean_text))
        course_desc_keywords = [
            "เรียนเกี่ยวกับอะไร","เรียนอะไร","คือวิชาอะไร",
            "สอนอะไร","สอนเกี่ยวกับอะไร","วิชานี้คืออะไร"
        ]
        course_code_match = re.search(r"([a-zA-Z]{2,4})\s*(\d{3})", clean_text)
        if (course_code_match or any(w in clean_text for w in course_desc_keywords)) and not _has_year_or_sem:
            return self._format_output(text, "course_desc", 1.0, is_fallback=True)

        # 12. Staff info
        staff_keywords = ["อาจารย์","อจ","ผู้สอน","ดร.","ดอกเตอร์","รศ.","ผศ.","สอน","lecturer"]
        if any(w in clean_text for w in staff_keywords):
            return self._format_output(text, "staff_info", 1.0, is_fallback=True)

        # 13. Curriculum (weak — หน่วยกิต/วิชาทั่วไป)
        curriculum_weak = ["เรียนยาก","หน่วยกิต","วิชา","ต้องเรียน","ลงทะเบียน"]
        if any(w in clean_text for w in curriculum_weak):
            return self._format_output(text, "curriculum_info", 1.0, is_fallback=True)

        # 14. Small talk
        if "ชื่อ" in clean_text and "อะไร" in clean_text:
            ignore = ["อาจารย์","จารย์","คณะ","สาขา","มหาลัย","วิชา","คณบดี","ผอ","ผู้อำนวยการ"]
            if not any(w in clean_text for w in ignore):
                return self._format_output(text, "small_talk", 1.0, is_fallback=True)

        closing = ["ขอบคุณ","แต๊งกิ้ว","บ๊ายบาย","บาย","bye","ขอบใจ","thank","thanks"]
        if any(w in text_lower for w in closing):
            return self._format_output(text, "small_talk", 1.0, is_fallback=True)

        # =========================================================
        # Model inference (ถ้าผ่าน rule ทั้งหมดแล้ว)
        # =========================================================
        inputs = self.tokenizer(
            clean_text, return_tensors="pt", truncation=True, padding=True, max_length=128
        )
        with torch.no_grad():
            outputs = self.model(**inputs)

        probs      = torch.softmax(outputs.logits, dim=1)[0]
        pred_id    = torch.argmax(outputs.logits, dim=1).item()
        raw_intent = self.label_encoder.inverse_transform([pred_id])[0]
        confidence = float(probs[pred_id].item())

        # Safety net: confidence ต่ำ
        if confidence < 0.50:
            _ents_safety = self._extract_entities(text)
            if _ents_safety.get("curriculum_year"):
                return self._format_output(text, "curriculum_info", confidence, is_fallback=True)
            return self._format_output(text, "out_of_scope", confidence, is_fallback=True)

        # Map model label ที่ไม่รู้จัก → out_of_scope
        if raw_intent not in DISPLAY_NAMES:
            return self._format_output(text, "out_of_scope", confidence, is_fallback=True)

        return self._format_output(text, raw_intent, confidence, is_fallback=False)

    def predict_as_json(self, text: str) -> str:
        return json.dumps(self.predict(text), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    clf = ThaiIntentClassifier()
    clf.load()
    tests = [
        # Greeting / small_talk
        ("สวัสดีครับ",                          "greeting"),
        ("ขอบคุณนะคะ",                           "small_talk"),
        # Major info (แยกจาก career)
        ("รายละเอียดสาขา",                        "career_info"),
        ("ข้อมูลสาขา AI and Data Science",        "career_info"),
        ("สาขานี้เรียนอะไรบ้าง",                  "career_info"),
        ("ห้องปฏิบัติการของสาขามีอะไรบ้าง",       "career_info"),
        # Career (อาชีพ/งาน)
        ("จบไปทำงานอะไรได้บ้าง",                  "career_info"),
        ("เงินเดือน AI engineer เป็นยังไง",       "career_info"),
        # Staff
        ("ดร. ใครสอนวิชา Machine Learning",       "staff_info"),
        # Coop
        ("สหกิจมีบริษัทอะไรบ้าง",                 "coop_intern"),
        # Admission
        ("ค่าเทอมปี 1 เท่าไหร่",                  "admission_info"),
        # MOU
        ("Huawei เป็น MOU กับสาขาไหม",            "mou_company"),
        # Report
        ("ระบบเน็ตล่ม เข้าไม่ได้เลย",             "report_issue"),
        # Out of scope
        ("ใครชนะบอลโลก 2026",                     "out_of_scope"),
        # Curriculum
        ("ปี 1 เทอม 1 ต้องเรียนอะไร",            "curriculum_info"),
        ("แผนปี 2567 ปี 1 เทอม 1 มีอะไร",        "curriculum_info"),
        ("แผนปี 2567 รุ่น 1/1 มีวิชาอะไร",        "curriculum_info"),
        ("แผนปกติ",                               "curriculum_info"),
        ("รุ่น 1/1",                              "curriculum_info"),
        ("ปี 2 เทอม 2 สหกิจ",                     "curriculum_info"),
        # cohort prefix
        ("นักศึกษา 65 ปี 3 เทอม 1 เรียนอะไร",     "curriculum_info"),
        # Course desc
        ("AIE455 เรียนเกี่ยวกับอะไร",              "course_desc"),
    ]
    print(f"\n{'คำถาม':<52} {'expect':<18} {'got':<18} {'conf':>6} {'✓/✗':>4}")
    print("-" * 105)
    ok = err = 0
    for q, expected in tests:
        r = clf.predict(q)
        got  = r["intent"]["label"]
        conf = r["intent"]["confidence"]
        mark = "✓" if got == expected else "✗"
        if got == expected: ok += 1
        else: err += 1
        print(f"{q[:52]:<52} {expected:<18} {got:<18} {conf:>6.2f} {mark:>4}")
    print(f"\nผล: {ok}/{ok+err} ถูก ({100*ok/(ok+err):.0f}%)")