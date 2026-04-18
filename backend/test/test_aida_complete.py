"""
test_aida_complete.py — AIDA Unified Test Suite
Path: backend/test/test_aida_complete.py

ทดสอบครบทุกด้านในไฟล์เดียว:
  Part A: Accuracy Test   — 30 คำถาม ตรวจคำตอบ LLM ว่าถูกต้องไหม
  Part B: Logic Test      — 7 Scenario ตรวจ flow (clarification, session, safety)

วิธีรัน:
  python backend/test/test_aida_complete.py            # ทั้งหมด
  python backend/test/test_aida_complete.py --part a   # เฉพาะ Accuracy
  python backend/test/test_aida_complete.py --part b   # เฉพาะ Logic
  python backend/test/test_aida_complete.py --id 3     # Accuracy ข้อ 3
  python backend/test/test_aida_complete.py --save     # บันทึก JSON report
  python backend/test/test_aida_complete.py --no-llm   # ข้าม LLM (Intent+RAG เท่านั้น)
"""

import sys, os, re, json, time, argparse
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "ai_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "database", "embeddings"))

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"
B="\033[1m";  D="\033[2m";  X="\033[0m";  M="\033[95m"; W="\033[97m"

# ══════════════════════════════════════════════════════════════════════════════
# PART A — ACCURACY TEST CASES (30 ข้อ)
# ══════════════════════════════════════════════════════════════════════════════
ACCURACY_CASES = [
    # กลุ่ม 1: หลักสูตรและแผนการเรียน
    {"id":1,  "cat":"curriculum_info",  "logic":"Filtering Year/Sem/Plan",
     "q":"หลักสูตร 2565 ปี 3 เทอม 1 แผนปกติ ต้องเรียนวิชาอะไรบ้าง?",
     "kw":["AIE311","AIE312","AIE313","วิศวกรรมซอฟต์แวร์","Software Engineering","ปฏิบัติการ"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องระบุรหัสวิชาหรือชื่อวิชา"},
    {"id":2,  "cat":"curriculum_info",  "logic":"Gap Check",
     "q":"หลักสูตร 2567 รุ่น 1/1 แผนปกติ ปี 2 เทอม 1 มีวิชา AIE213 ไหม?",
     "kw":["AIE213","Computer Programming","มี"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องยืนยันว่า 'มี'"},
    {"id":3,  "cat":"curriculum_info",  "logic":"Header Matching (กับดัก 2568)",
     "q":"หลักสูตร 2568 รุ่น 1/1 ปี 1 เทอม 2 แผนปกติ เรียนกี่หน่วยกิต?",
     "kw":["21"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องตอบ 21 หน่วยกิต — คำถามกับดักหลัก"},
    {"id":4,  "cat":"curriculum_info",  "logic":"Summer Logic",
     "q":"ถ้าเป็นเด็กปี 2568 รุ่น 2 ช่วงซัมเมอร์ปี 1 ต้องลงเรียนวิชาอะไร?",
     "kw":["ME154","GE011","MA109"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุรหัสวิชาภาคฤดูร้อน"},
    {"id":5,  "cat":"curriculum_info",  "logic":"Plan Comparison",
     "q":"วิชาเลือกเสรีของปี 2566 แผนสหกิจ เริ่มเรียนเทอมไหน?",
     "kw":["ฤดูร้อน","ปี 2","2"],  "min_kw":1,
     "emotion":["Talking","Curious"],  "note":"ต้องระบุภาคเรียน"},
    # กลุ่ม 2: คำอธิบายรายวิชา
    {"id":6,  "cat":"course_desc",  "logic":"Content Retrieval",
     "q":"วิชา AIE121 Real-life Data Challenges เรียนเกี่ยวกับเรื่องอะไรบ้าง?",
     "kw":["PDPA","Churn","Fraud","Segmentation","ข้อมูลธุรกิจ","การวิเคราะห์","Real-life","Data"],  "min_kw":2,
     "emotion":["Talking","Curious"],  "note":"ต้องระบุ topic"},
    {"id":7,  "cat":"course_desc",  "logic":"Keyword Search",
     "q":"วิชาอะไรที่สอนเรื่อง Machine Learning Operations และ CI/CD?",
     "kw":["AIE470","MLOps"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องระบุ AIE470"},
    {"id":8,  "cat":"course_desc",  "logic":"Comparison Logic",
     "q":"วิชา AIE455 และ AIE466 มีเนื้อหาแตกต่างกันอย่างไร?",
     "kw":["NLP","Natural Language","Robotics"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องอธิบายความต่าง"},
    {"id":9,  "cat":"course_desc",  "logic":"Relationship Extraction",
     "q":"วิชา MA109 Calculus II มีวิชาบังคับก่อน (Prerequisite) คืออะไร?",
     "kw":["MA108","Calculus I"],  "min_kw":1,
     "emotion":["Talking","Curious"],  "note":"อาจไม่มีใน KB → Curious ยอมรับ"},
    # กลุ่ม 3: ค่าเทอมและการเงิน
    {"id":10, "cat":"admission_info",  "logic":"Summation",
     "q":"ค่าเทอมปี 1 (รวมเทอม 1/1, 1/2 และ 2) แบบชำระเต็มจำนวนเป็นเงินกี่บาท?",
     "kw":["99,580","99580","99,400","รวม","ปีที่ 1","ทั้งปี"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องตอบยอดรวมปี 1"},
    {"id":11, "cat":"admission_info",  "logic":"Specific Row",
     "q":"ถ้ากู้ กยศ. (ลักษณะ 2) ปี 3 เทอม 1 ต้องเตรียมเงินส่วนต่างเองเท่าไหร่?",
     "kw":["23,800","23800"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องตอบ 23,800"},
    {"id":12, "cat":"admission_info",  "logic":"Total Sum",
     "q":"รวมค่าใช้จ่ายส่วนต่าง กยศ. ตลอดหลักสูตร 4 ปี คือกี่บาท?",
     "kw":["95,780","95780","รวม","กยศ","ส่วนต่าง","4 ปี"],  "min_kw":1,
     "emotion":["Talking","Curious"],  "note":"KB อาจไม่มียอดรวม กยศ. 4 ปี → Curious ยอมรับ"},
    {"id":13, "cat":"admission_info",  "logic":"Comparative Logic",
     "q":"ค่าเทอมเทอมไหนแพงที่สุดในหลักสูตร 4 ปี และราคาเท่าไหร่?",
     "kw":["ปี 3","เทอม 1","58,800","58800"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุ ปี 3 เทอม 1 และ 58,800"},
    # กลุ่ม 4: สหกิจศึกษา
    {"id":14, "cat":"coop_intern",  "logic":"Threshold Logic",
     "q":"ถ้าเกรดเฉลี่ย (GPAX) 2.65 สามารถสมัครสหกิจศึกษาได้ไหม?",
     "kw":["2.75","ไม่","ต้อง"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องตอบว่าไม่ได้ เกณฑ์ 2.75"},
    {"id":15, "cat":"coop_intern",  "logic":"Structural Comparison",
     "q":"การฝึกงานทั่วไปต่างจากสหกิจศึกษาในแง่หน่วยกิตอย่างไร?",
     "kw":["0","1","6","9","หน่วยกิต"],  "min_kw":3,
     "emotion":["Talking"],  "note":"ต้องระบุหน่วยกิตทั้งสองประเภท"},
    {"id":16, "cat":"coop_intern",  "logic":"Timeline",
     "q":"ช่วงปฏิบัติงานสหกิจศึกษาของปี 2568 คือช่วงเดือนไหน?",
     "kw":["มิถุนายน","มิ.ย","พฤศจิกายน","พ.ย","2569"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุเดือนเริ่ม-สิ้นสุด"},
    {"id":17, "cat":"coop_intern",  "logic":"Course Timing",
     "q":"วิชา CO301 ต้องเรียนในชั้นปีไหนและเทอมไหน?",
     "kw":["ปี 3","ปีที่ 3","ภาคการศึกษาที่ 2","เทอม 2"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุปีที่ 3 เทอม 2"},
    # กลุ่ม 5: MOU
    {"id":18, "cat":"mou_company",  "logic":"Semantic Search",
     "q":"บริษัทใดเชี่ยวชาญด้าน RPA และช่วยลด Human Error ได้?",
     "kw":["UiPath","RPA"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องตอบ UiPath"},
    {"id":19, "cat":"mou_company",  "logic":"Content Extraction",
     "q":"บริษัท Huawei Technologies ให้บริการโซลูชั่นด้านใดบ้าง?",
     "kw":["ICT","Cloud","Network"],  "min_kw":1,
     "emotion":["Talking"],  "note":"ต้องระบุบริการหลัก"},
    {"id":20, "cat":"mou_company",  "logic":"Domain Specific",
     "q":"ซอฟต์แวร์ Mango ERP เหมาะกับธุรกิจประเภทใด?",
     "kw":["รับเหมา","อสังหาริมทรัพย์","Mango"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุประเภทธุรกิจ"},
    # กลุ่ม 6: อาจารย์และบุคลากร
    {"id":21, "cat":"staff_info",  "logic":"Cross-Search MOU↔Staff",
     "q":"มีอาจารย์พิเศษคนไหนมาจากบริษัท Softnix Technology บ้าง?",
     "kw":["ชาคริต","ผาอินทร์","Softnix"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุชื่อ คุณชาคริต"},
    {"id":22, "cat":"staff_info",  "logic":"Entity Linking",
     "q":"ใครคืออาจารย์ที่จบจาก MIT และเชี่ยวชาญด้าน ML?",
     "kw":["ภูมิพัฒ","MIT"],  "min_kw":1,
     "emotion":["Talking","Curious"],  "note":"ต้องระบุชื่ออาจารย์"},
    {"id":23, "cat":"staff_info",  "logic":"Expertise Retrieval",
     "q":"ดร.ปัญจวี รักประยูร เชี่ยวชาญด้านใดเป็นพิเศษ?",
     "kw":["Computer Vision","Robotics","3D","ปัญจวี"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุความเชี่ยวชาญ"},
    # กลุ่ม 7: Lab/สาขา
    {"id":24, "cat":"career_info",  "logic":"Facility Mapping",
     "q":"ห้องปฏิบัติการ AI Innovation Lab ตั้งอยู่ที่ห้องหมายเลขใด?",
     "kw":["B4","302","B4-302","B4 302"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุ B4-302"},
    {"id":25, "cat":"career_info",  "logic":"Content Extraction",
     "q":"ศูนย์วิจัย BU CROCCS เน้นวิจัยด้านใดบ้าง?",
     "kw":["สื่อสาร","ภาพ","นาโน","CROCCS"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุสาขาวิจัย"},
    {"id":26, "cat":"career_info",  "logic":"Career Association",
     "q":"จบสาขา AIDA ไปประกอบอาชีพเป็นอะไรได้บ้าง? (ขอ 3 ตัวอย่าง)",
     "kw":["AI Engineer","Data Scientist","MLOps","วิศวกร"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุอาชีพอย่างน้อย 2 อย่าง"},
    # กลุ่ม 8: ข้อมูลทั่วไป
    {"id":27, "cat":"general_info",  "logic":"Route Navigation",
     "q":"ถ้าจะเดินทางมา ม.กรุงเทพ ด้วยรถไฟฟ้า BTS ต้องลงสถานีไหน?",
     "kw":["หมอชิต","อนุสาวรีย์","คปอ"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุสถานีอย่างน้อย 2 แห่ง"},
    {"id":28, "cat":"general_info",  "logic":"Admin Procedure",
     "q":"จบ ปวส. มา อยากสมัครเทียบโอน ต้องใช้เอกสารอะไรและเสียค่าธรรมเนียมกี่บาท?",
     "kw":["1,000","1000","รบ.1","บัตร"],  "min_kw":2,
     "emotion":["Talking"],  "note":"ต้องระบุค่าธรรมเนียม 1,000"},
    {"id":29, "cat":"general_info",  "logic":"Location",
     "q":"คณะวิศวกรรมศาสตร์ ม.กรุงเทพ ตั้งอยู่ที่อาคารไหน ชั้นอะไร?",
     "kw":["B4","ชั้น 2","ชั้น2","วิศวกรรม","อาคาร"],  "min_kw":1,
     "emotion":["Talking","Curious"],  "note":"KB อาจไม่มี exact phrase B4 ชั้น 2 → Curious ยอมรับ"},
    # กลุ่ม 9: Safety
    {"id":30, "cat":"out_of_scope",  "logic":"Guardrail",
     "q":"เย็นนี้กินอะไรดี แนะนำเมนูอาหารหน่อย",
     "kw":["นอกเหนือ","ขอบเขต"],  "min_kw":1,
     "emotion":["Curious"],  "note":"ต้องปฏิเสธและแจ้งนอกขอบเขต"},
]

# ══════════════════════════════════════════════════════════════════════════════
# PART B — LOGIC TEST SCENARIOS (7 scenarios, multi-turn)
# ══════════════════════════════════════════════════════════════════════════════
LOGIC_SCENARIOS = [
    {
        "id": "B1", "name": "Multi-turn Clarification (3 ขั้น)",
        "desc": "ตรวจว่า Session จำ entities ข้ามรอบได้ และถามกลับครบ 3 ขั้น",
        "steps": [
            {"q": "ปี 1 เทอม 1 ต้องเรียนอะไร",
             "expect_source": "clarify", "expect_in": ["ปีหลักสูตร","หลักสูตร"],
             "label": "ขั้น 1: ถามปีหลักสูตร"},
            {"q": "2567",
             "expect_source": "clarify", "expect_in": ["รุ่น","generation"],
             "label": "ขั้น 2: ถามรุ่น"},
            {"q": "รุ่น 1/1",
             "expect_source": "clarify", "expect_in": ["แผน","ปกติ","สหกิจ"],
             "label": "ขั้น 3: ถามแผน"},
            {"q": "แผนปกติ",
             "expect_source": "llm", "expect_in": ["GE","AIE","หน่วยกิต","วิชา"],
             "label": "ขั้น 4: ตอบจริง"},
        ]
    },
    {
        "id": "B2", "name": "Exact Pre-filter (Regex Space)",
        "desc": "ตรวจว่า 'AIE 121' (มีช่องว่าง) ค้นหาได้เหมือน 'AIE121'",
        "steps": [
            {"q": "วิชา AIE455 สอนเรื่องอะไร",
             "expect_source": "llm", "expect_in": ["NLP","Natural Language","455"],
             "label": "รหัสไม่มีช่องว่าง"},
            {"q": "วิชา AIE 121 เรียนเกี่ยวกับอะไร",
             "expect_source": "llm", "expect_in": ["Real-life","Data","121","Challenges"],
             "label": "รหัสมีช่องว่าง — ต้องเจอเหมือนกัน"},
        ]
    },
    {
        "id": "B3", "name": "Arithmetic & Financial Reasoning",
        "desc": "ตรวจว่า LLM คำนวณตัวเลขทางการเงินได้ถูกต้อง",
        "steps": [
            {"q": "ค่าเทอมปี 3 เทอม 1 ยอดเต็มคือเท่าไหร่",
             "expect_source": "llm", "expect_in": ["82,600","82600","58,800","23,800"],
             "label": "บวกเลข: 58,800 + 23,800 = 82,600"},
            {"q": "รวมค่าใช้จ่ายตลอดหลักสูตร 4 ปี แบบชำระเต็มจำนวน",
             "expect_source": "llm", "expect_in": ["374,980","374980","374","รวม","ตลอดหลักสูตร"],
             "label": "ยอดรวม 4 ปี"},
        ]
    },
    {
        "id": "B4", "name": "Semantic Search & Cross-Category",
        "desc": "ตรวจว่าค้นหาแบบ semantic และข้ามหมวดหมู่ได้",
        "steps": [
            {"q": "บริษัทที่ทำเรื่อง Robot มีใครบ้าง",
             "expect_source": "llm", "expect_in": ["DNA","Robotics","IIS","Robot"],
             "label": "Semantic: Robot → DNA Robotics, IIS"},
            {"q": "มีอาจารย์พิเศษจาก Softnix Technology ไหม",
             "expect_source": "llm", "expect_in": ["ชาคริต","Softnix"],
             "label": "Cross-search: MOU → staff_info"},
        ]
    },
    {
        "id": "B5", "name": "Rule-based Threshold & Timeline",
        "desc": "ตรวจว่าระบบดึงกฎและเงื่อนไขได้ถูกต้อง",
        "steps": [
            {"q": "เกรดเฉลี่ย 2.50 ไปสหกิจศึกษาได้ไหม",
             "expect_source": "llm", "expect_in": ["2.75","ไม่","ต้องมี"],
             "label": "Threshold: ต้อง 2.75 ขึ้นไป"},
            {"q": "วิชา CO301 เตรียมสหกิจต้องเรียนตอนไหน",
             "expect_source": "llm", "expect_in": ["ปี 3","เทอม 2","ภาคการศึกษาที่ 2"],
             "label": "Timeline: ปี 3 เทอม 2"},
        ]
    },
    {
        "id": "B6", "name": "Safety & Canned Responses",
        "desc": "ตรวจว่า guardrail ทำงาน — ไม่ผ่าน RAG/LLM",
        "steps": [
            {"q": "มึงโง่จัง",
             "expect_source": "canned", "expect_in": ["สุภาพ","ลองถาม"],
             "label": "Toxic → block"},
            {"q": "ขอสูตรทำต้มยำกุ้งหน่อย",
             "expect_source": "canned", "expect_in": ["นอกเหนือ","ขอบเขต"],
             "label": "Out-of-scope → reject"},
            {"q": "สวัสดี",
             "expect_source": "canned", "expect_in": ["AIDA","สวัสดี"],
             "label": "Greeting → canned response"},
        ]
    },
    {
        "id": "B7", "name": "Summer & Special Semester",
        "desc": "ตรวจว่าตรวจจับ 'ซัมเมอร์' และ 'ฤดูร้อน' ได้",
        "steps": [
            {"q": "เด็กปี 2567 รุ่น 2 ช่วงซัมเมอร์ปี 1 แผนปกติ เรียนวิชาอะไร",
             "expect_source": "llm", "expect_in": ["ME154","GE101","MA109","9"],
             "label": "Summer 2567 รุ่น 2 → 9 หน่วยกิต"},
            {"q": "ภาคฤดูร้อนปี 1 หลักสูตร 2568 รุ่น 1/1 แผนปกติ มีวิชาอะไรบ้าง",
             "expect_source": "llm", "expect_in": ["ฤดูร้อน","summer","วิชา","หน่วยกิต"],
             "label": "Summer 2568 รุ่น 1/1"},
        ]
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# SESSION HELPER
# ══════════════════════════════════════════════════════════════════════════════

class Session:
    """จำ entities ข้ามรอบ สำหรับ multi-turn clarification"""
    def __init__(self):
        self.ctx: dict = {}

    def update(self, entities: dict):
        for k, v in entities.items():
            if v and k != "keywords":
                self.ctx[k] = v

    def merge_into(self, intent_result: dict) -> dict:
        merged = dict(self.ctx)
        merged.update({k: v for k, v in intent_result.get("entities", {}).items() if v})
        intent_result = dict(intent_result)
        intent_result["entities"] = merged
        # อัปเดต display_name ถ้ามี curriculum_year
        cy = merged.get("curriculum_year", "")
        if cy and "curriculum_info" == intent_result.get("intent", {}).get("label", ""):
            dn = f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี{cy}]"
            intent_result.setdefault("intent", {})["display_name"] = dn
        return intent_result

    def clear(self):
        self.ctx = {}

    def inject_bare_answer(self, text: str, intent_result: dict) -> dict:
        """แปลงคำตอบ bare ('2567', 'รุ่น 1/1', 'แผนปกติ') → entities"""
        import re as re_mod
        ents = intent_result.get("entities", {})
        # ปีหลักสูตร
        if re_mod.fullmatch(r"256[5-9]", text.strip()):
            ents["curriculum_year"] = text.strip()
        # รุ่น
        m = re_mod.search(r"รุ่น\s*([\d/]+)", text)
        if m: ents["generation"] = m.group(1)
        # แผน
        if "สหกิจ" in text: ents["plan"] = "สหกิจ"
        elif "ปกติ" in text: ents["plan"] = "ปกติ"
        intent_result = dict(intent_result); intent_result["entities"] = ents
        return intent_result


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_single(q: str, clf, rag, llm, RF, session: Session, run_llm: bool):
    """รัน 1 turn ของ pipeline"""
    from rag_handler import CLARIFICATION_NEEDED

    intent_result = clf.predict(q)
    intent_result = session.inject_bare_answer(q, intent_result)
    intent_result = session.merge_into(intent_result)

    # Pre-check (canned / clarification)
    pre = RF.handle_no_retrieval(intent_result)
    if pre:
        is_clarify = pre.get("response_metadata", {}).get("is_clarification", False)
        source = "clarify" if is_clarify else "canned"
        if is_clarify:
            session.update(intent_result.get("entities", {}))
        else:
            session.clear()
        return {
            "source":       source,
            "intent_label": intent_result.get("intent", {}).get("label", ""),
            "display_text": pre.get("display_text", ""),
            "speech_text":  pre.get("speech_text", ""),
            "emotion":      pre.get("emotion", ""),
            "chunks_count": 0,
        }

    # RAG
    chunks = rag.retrieve(q, intent_result)
    if chunks == CLARIFICATION_NEEDED:
        session.update(intent_result.get("entities", {}))
        return {
            "source": "clarify", "intent_label": intent_result.get("intent",{}).get("label",""),
            "display_text": "ต้องการข้อมูลเพิ่มเติม", "speech_text": "",
            "emotion": "Curious", "chunks_count": 0,
        }

    chunks_count = len(chunks) if isinstance(chunks, list) else 0
    display_text = speech_text = emotion = ""

    if run_llm and chunks_count > 0:
        resp = llm.generate_response(query=q, retrieval_results=chunks,
                                      intent_result=intent_result)
        if resp:
            formatted = RF.format_output(resp, intent_result)
            display_text = formatted.get("display_text", "")
            speech_text  = formatted.get("speech_text", "")
            emotion      = formatted.get("emotion", "")

    session.clear()
    return {
        "source":       "llm",
        "intent_label": intent_result.get("intent", {}).get("label", ""),
        "display_text": display_text,
        "speech_text":  speech_text,
        "emotion":      emotion,
        "chunks_count": chunks_count,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART A: ACCURACY EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

def eval_accuracy(tc: dict, result: dict) -> dict:
    display = result.get("display_text", "")
    speech  = result.get("speech_text", "")
    emotion = result.get("emotion", "")

    kw_found = [kw for kw in tc["kw"] if kw.lower() in display.lower()]
    kw_pass  = len(kw_found) >= tc.get("min_kw", 1)

    em_pass  = emotion in tc["emotion"]
    sym_pass = not any(c in (speech or "") for c in ["*","#","|","_"])
    notempty = len((display or "").strip()) > 10
    haschunk = result.get("chunks_count", 0) > 0 or tc["cat"] in ("out_of_scope","greeting")

    checks = [
        {"n":"keywords",   "p":kw_pass,  "d":f"พบ {len(kw_found)}/{len(tc['kw'])}: {kw_found}"},
        {"n":"emotion",    "p":em_pass,  "d":f"got='{emotion}' exp={tc['emotion']}"},
        {"n":"no_symbols", "p":sym_pass, "d":"clean" if sym_pass else "found symbols"},
        {"n":"not_empty",  "p":notempty, "d":f"len={len(display or '')}"},
        {"n":"has_chunks", "p":haschunk, "d":f"chunks={result.get('chunks_count',0)}"},
    ]
    return {"overall": all(c["p"] for c in checks), "checks": checks}


def run_accuracy_case(tc: dict, clf, rag, llm, RF, run_llm: bool) -> dict:
    """รัน 1 accuracy test case — auto-handle clarification"""
    session = Session()
    q = tc["q"]
    final = None

    for turn in range(5):
        try:
            r = run_single(q, clf, rag, llm, RF, session, run_llm)
        except Exception as e:
            return {**tc, "overall_pass": False, "eval": {"overall":False,"checks":[]},
                    "intent_label":"error", "emotion":"", "chunks_count":0,
                    "display_text":str(e), "speech_text":"", "turns":turn+1}

        if r["source"] != "clarify":
            final = r; break

        # auto-respond to clarification
        step_text = r.get("display_text","")
        if "ปีหลักสูตร" in step_text or "ปีไหน" in step_text:
            m = re.search(r"(256[5-9])", tc["q"])
            q = m.group(1) if m else "2567"
        elif "รุ่น" in step_text:
            m = re.search(r"รุ่น\s*([\d/]+)", tc["q"])
            q = f"รุ่น {m.group(1)}" if m else "รุ่น 1/1"
        elif "แผน" in step_text:
            q = "แผนสหกิจศึกษา" if "สหกิจ" in tc["q"] else "แผนปกติ"
        else:
            final = r; break

    if not final:
        final = r if r else {"display_text":"","speech_text":"","emotion":"","chunks_count":0,"intent_label":""}

    ev = eval_accuracy(tc, final)
    return {
        **tc,
        "overall_pass":  ev["overall"],
        "eval":          ev,
        "intent_label":  final.get("intent_label",""),
        "emotion":       final.get("emotion",""),
        "chunks_count":  final.get("chunks_count",0),
        "display_text":  final.get("display_text",""),
        "speech_text":   final.get("speech_text",""),
        "turns":         turn + 1,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART B: LOGIC EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

def run_logic_scenario(sc: dict, clf, rag, llm, RF, run_llm: bool) -> dict:
    """รัน 1 logic scenario — multi-turn"""
    session = Session()
    step_results = []

    for step in sc["steps"]:
        q = step["q"]
        try:
            r = run_single(q, clf, rag, llm, RF, session, run_llm)
        except Exception as e:
            r = {"source":"error","display_text":str(e),"speech_text":"",
                 "emotion":"","chunks_count":0,"intent_label":"error"}

        display = r.get("display_text","")
        got_src = r.get("source","")
        exp_src = step.get("expect_source","")
        exp_in  = step.get("expect_in",[])

        src_pass = (exp_src == "" or got_src == exp_src)
        kw_pass  = any(kw.lower() in display.lower() for kw in exp_in) if exp_in else True
        step_pass = src_pass and kw_pass

        step_results.append({
            "label":    step["label"],
            "q":        q,
            "source":   got_src,
            "pass":     step_pass,
            "src_pass": src_pass,
            "kw_pass":  kw_pass,
            "found_kw": [kw for kw in exp_in if kw.lower() in display.lower()],
            "display_preview": display[:120],
        })

        if run_llm and got_src == "llm":
            time.sleep(0.5)

    overall = all(s["pass"] for s in step_results)
    return {
        "id":           sc["id"],
        "name":         sc["name"],
        "desc":         sc["desc"],
        "steps":        step_results,
        "overall_pass": overall,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRINT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def print_accuracy_result(r: dict, verbose: bool):
    icon = f"{G}✅{X}" if r["overall_pass"] else f"{R}❌{X}"
    print(f"\n{icon} [{r['id']:02d}] {B}{r['q'][:58]}{X}")
    print(f"   {D}{r['logic']} | {r['cat']}{X}")
    print(f"   Intent:{C}{r['intent_label']}{X}  Emotion:{M}{r['emotion']}{X}  "
          f"Chunks:{r['chunks_count']}  Turns:{r['turns']}")
    for c in r["eval"]["checks"]:
        sym = f"{G}✓{X}" if c["p"] else f"{R}✗{X}"
        print(f"   {sym} {c['n']:12s} {c['d']}")
    if verbose and r.get("display_text"):
        print(f"   {D}→ {r['display_text'][:160]}{X}")
    if r.get("note"):
        print(f"   {Y}※ {r['note']}{X}")


def print_logic_result(sc: dict, verbose: bool):
    icon = f"{G}✅{X}" if sc["overall_pass"] else f"{R}❌{X}"
    print(f"\n{icon} {B}[{sc['id']}] {sc['name']}{X}")
    print(f"   {D}{sc['desc']}{X}")
    for s in sc["steps"]:
        step_icon = f"{G}✓{X}" if s["pass"] else f"{R}✗{X}"
        src_color = G if s["src_pass"] else R
        kw_color  = G if s["kw_pass"]  else R
        print(f"   {step_icon} {s['label']}")
        print(f"      Q: {D}{s['q'][:55]}{X}")
        print(f"      source={src_color}{s['source']}{X}  "
              f"kw={kw_color}{s['found_kw']}{X}")
        if verbose:
            print(f"      {D}→ {s['display_preview']}{X}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AIDA Complete Test Suite")
    parser.add_argument("--part",    choices=["a","b"], help="a=Accuracy, b=Logic")
    parser.add_argument("--id",      type=int,  help="Accuracy: รัน test id เดียว")
    parser.add_argument("--cat",     type=str,  help="Accuracy: กรอง category")
    parser.add_argument("--no-llm",  action="store_true")
    parser.add_argument("--save",    action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    run_llm = not args.no_llm

    # ── Load pipeline ──────────────────────────────────────────────────────────
    print(f"\n{B}{'='*65}{X}")
    print(f"{B}  AIDA Complete Test Suite — {datetime.now().strftime('%Y-%m-%d %H:%M')}{X}")
    print(f"{B}{'='*65}{X}")
    print(f"  Mode: {'Part A+B (Full)' if not args.part else 'Part '+args.part.upper()}"
          f"  |  LLM: {'ON' if run_llm else f'{Y}OFF{X}'}\n")

    try:
        from intent_classifier import ThaiIntentClassifier
        from rag_handler import RAGHandler
        from llm_interface import LLMInterface
        from response_formatter import ResponseFormatter

        print(f"{C}กำลังโหลด pipeline...{X}")
        clf = ThaiIntentClassifier(); clf.load()
        rag = RAGHandler()
        llm = LLMInterface() if run_llm else None
        RF  = ResponseFormatter
        print(f"{G}โหลดสำเร็จ ✓{X}")
    except Exception as e:
        print(f"{R}[ERROR] โหลดไม่ได้: {e}{X}"); return

    start = time.time()
    report = {"timestamp": datetime.now().isoformat(), "run_llm": run_llm,
              "accuracy": {}, "logic": {}}

    # ══════════════════════════════════════════════════════════════════════════
    # PART A
    # ══════════════════════════════════════════════════════════════════════════
    if args.part != "b":
        cases = ACCURACY_CASES
        if args.id:   cases = [tc for tc in cases if tc["id"] == args.id]
        if args.cat:  cases = [tc for tc in cases if tc["cat"] == args.cat]

        print(f"\n{B}{W}{'━'*65}")
        print(f"  PART A — Accuracy Test ({len(cases)} cases)")
        print(f"{'━'*65}{X}")

        acc_results = []
        for tc in cases:
            print(f"{D}  ────────────────────────────────────────{X}", end="", flush=True)
            r = run_accuracy_case(tc, clf, rag, llm, RF, run_llm)
            print(f"\r", end="")
            print_accuracy_result(r, args.verbose)
            acc_results.append(r)
            if run_llm: time.sleep(0.8)

        # Summary A
        a_pass = sum(1 for r in acc_results if r["overall_pass"])
        a_fail = len(acc_results) - a_pass
        a_pct  = a_pass / len(acc_results) * 100 if acc_results else 0

        print(f"\n{B}  Part A Summary:{X}")
        print(f"  ผ่าน {G}{a_pass}{X} / {len(acc_results)}  ({G if a_pct>=80 else Y if a_pct>=60 else R}{a_pct:.1f}%{X})")

        # Category breakdown
        cat_stats = defaultdict(lambda:{"p":0,"t":0})
        for r in acc_results:
            cat_stats[r["cat"]]["t"] += 1
            if r["overall_pass"]: cat_stats[r["cat"]]["p"] += 1
        for cat, s in sorted(cat_stats.items()):
            pct  = s["p"]/s["t"]*100
            bar  = "█"*int(pct//10) + "░"*(10-int(pct//10))
            col  = G if pct>=80 else Y if pct>=60 else R
            print(f"  {cat:22s} [{bar}] {col}{s['p']}/{s['t']}{X}")

        if a_fail:
            print(f"\n  {R}Failed:{X}", end=" ")
            print(", ".join(f"#{r['id']}" for r in acc_results if not r["overall_pass"]))

        report["accuracy"] = {
            "total": len(acc_results), "passed": a_pass,
            "failed": a_fail, "pass_rate": round(a_pct,1),
            "results": acc_results
        }

    # ══════════════════════════════════════════════════════════════════════════
    # PART B
    # ══════════════════════════════════════════════════════════════════════════
    if args.part != "a":
        print(f"\n{B}{W}{'━'*65}")
        print(f"  PART B — Logic Test ({len(LOGIC_SCENARIOS)} scenarios)")
        print(f"{'━'*65}{X}")

        logic_results = []
        for sc in LOGIC_SCENARIOS:
            r = run_logic_scenario(sc, clf, rag, llm, RF, run_llm)
            print_logic_result(r, args.verbose)
            logic_results.append(r)

        # Summary B
        b_pass = sum(1 for r in logic_results if r["overall_pass"])
        b_fail = len(logic_results) - b_pass
        b_pct  = b_pass / len(logic_results) * 100 if logic_results else 0

        print(f"\n{B}  Part B Summary:{X}")
        print(f"  ผ่าน {G}{b_pass}{X} / {len(logic_results)}  ({G if b_pct>=80 else Y if b_pct>=60 else R}{b_pct:.1f}%{X})")

        if b_fail:
            print(f"  {R}Failed:{X}", end=" ")
            print(", ".join(r["id"] for r in logic_results if not r["overall_pass"]))

        report["logic"] = {
            "total": len(logic_results), "passed": b_pass,
            "failed": b_fail, "pass_rate": round(b_pct,1),
            "results": logic_results
        }

    # ══════════════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    elapsed = time.time() - start
    print(f"\n{B}{'='*65}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*65}{X}")
    if "total" in report.get("accuracy", {}):
        a = report["accuracy"]
        print(f"  Part A Accuracy : {G if a['pass_rate']>=80 else Y}{a['pass_rate']}%{X} ({a['passed']}/{a['total']})")
    if "total" in report.get("logic", {}):
        b = report["logic"]
        print(f"  Part B Logic    : {G if b['pass_rate']>=80 else Y}{b['pass_rate']}%{X} ({b['passed']}/{b['total']})")
    print(f"  เวลาทั้งหมด      : {elapsed:.1f}s")
    print(f"{'='*65}{X}")

    if args.save:
        report["elapsed_s"] = round(elapsed,1)
        fname = f"test_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fname,"w",encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n{G}บันทึก report: {fname}{X}")


if __name__ == "__main__":
    main()