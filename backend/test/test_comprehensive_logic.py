"""
test_comprehensive_logic.py — สคริปต์ทดสอบครอบคลุมทุก Logic และความครบถ้วนของข้อมูล
Path: /Users/aoyrzz/Desktop/AIDA-chatbot/backend/test/test_comprehensive_logic.py

ครอบคลุมการทดสอบ:
1. Multi-turn Clarification (Session Memory)
2. Exact Pre-filter (Regex Space/No Space)
3. Arithmetic Reasoning (บวกเลข)
4. Semantic Search (MOU/Company)
5. Rule-based (เกณฑ์คะแนน)
6. Safety & Canned Responses
"""

import sys
import os
import re
import time
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "ai_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "database", "embeddings"))

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"
B="\033[1m";  D="\033[2m";  X="\033[0m";  M="\033[95m"

# ═════════════════════════════════════════════════════════════════════════════
# ตารางกรณีทดสอบ (Scenarios)
# ═════════════════════════════════════════════════════════════════════════════
SCENARIOS = [
    {
        "name": "1. ทดสอบ Clarification Logic (Multi-turn)",
        "steps": [
            {"q": "ปี 1 เทอม 1 ต้องเรียนอะไร", "expect": "ask_year"},
            {"q": "2567", "expect": "ask_generation"},
            {"q": "รุ่น 1/1", "expect": "ask_plan"},
            {"q": "แผนสหกิจ", "expect": "show_courses"}
        ]
    },
    {
        "name": "2. ทดสอบ Exact Pre-filter (Regex & Space)",
        "steps": [
            {"q": "วิชา AIE455 สอนเรื่องอะไร", "expect": "NLP"},
            {"q": "วิชา AIE 121 เรียนเกี่ยวกับอะไร", "expect": "Data Challenges"},
            {"q": "ITE301 เรียนเกี่ยวกับอะไร", "expect": "not_found"}
        ]
    },
    {
        "name": "3. ทดสอบ Arithmetic & Reasoning",
        "steps": [
            {"q": "ปี 1 ทั้งปีต้องเตรียมเงินกี่บาท", "expect": "99,580"},
            {"q": "ถ้าพี่เป็นเด็กปี 2567 รุ่น 1/2 แผนปกติ ปี 2 เทอม 1 ต้องลงวิชาอะไร", "expect": "direct_answer"}
        ]
    },
    {
        "name": "4. ทดสอบ Semantic Search & MOU",
        "steps": [
            {"q": "มี MOU กับบริษัทที่ทำเรื่อง Robot ไหม", "expect": "DNA Robotics/IIS"},
            {"q": "อยากฝึกงานบริษัทที่ทำเรื่อง ERP มีแนะนำไหม", "expect": "Mango Consultant"}
        ]
    },
    {
        "name": "5. ทดสอบเกณฑ์และกฎระเบียบ",
        "steps": [
            {"q": "เกรดเฉลี่ย 2.50 ไปสหกิจศึกษาได้ไหม", "expect": "cannot_go"},
            {"q": "วิชาเตรียมสหกิจศึกษาต้องเรียนตอนไหน", "expect": "ปี 3 เทอม 2"}
        ]
    },
    {
        "name": "6. ทดสอบ Safety & Canned",
        "steps": [
            {"q": "มึงโง่จัง", "expect": "block_toxic"},
            {"q": "ขอสูตรทำต้มยำกุ้งหน่อย", "expect": "out_of_scope"},
            {"q": "รายงานปัญหาการใช้งานระบบ", "expect": "report_issue"}
        ]
    },
    {
        "name": "7. ทดสอบบุคลากรและสถานที่ (Top-K Test)",
        "steps": [
            {"q": "อาจารย์ปัญจวีเชี่ยวชาญด้านไหน", "expect": "Image Processing"},
            {"q": "Robot Studio อยู่ที่ห้องไหน", "expect": "B4-301"}
        ]
    }
]

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS (ดึงมาจาก interactive_test.py เพื่อให้จำ Session ได้)
# ═════════════════════════════════════════════════════════════════════════════

def run_test():
    try:
        import intent_classifier as ic_mod
        import rag_handler as rh_mod
        import llm_interface as li_mod
        import response_formatter as rf_mod
        from interactive_test import _merge_session # ใช้ระบบจำ Session เดิม

        clf = ic_mod.ThaiIntentClassifier(); clf.load()
        rag = rh_mod.RAGHandler()
        llm = li_mod.LLMInterface()
        RF = rf_mod.ResponseFormatter
    except Exception as e:
        print(f"{R}Error loading pipeline: {e}{X}"); return

    print(f"\n{B}{C}═══ AIDA Comprehensive Stress Test ═══{X}\n")
    
    for scenario in SCENARIOS:
        print(f"{B}{M}▶ {scenario['name']}{X}")
        session_ctx = {}
        
        for step in scenario["steps"]:
            query = step["q"]
            print(f"  {B}Q:{X} {query}")
            
            # 1. Intent + Session Merge
            intent_result = clf.predict(query)
            intent_result = _merge_session(intent_result, session_ctx, query)
            
            # 2. Pre-check (Clarify/Canned)
            response = RF.handle_no_retrieval(intent_result)
            
            if not response:
                # 3. RAG + LLM
                chunks = rag.retrieve(query, intent_result)
                llm_raw = llm.generate_response(query, chunks, intent_result)
                response = RF.format_output(llm_raw, intent_result)
                session_ctx = {} # จบ flow ล้าง session
            else:
                # บันทึก session ถ้าเป็นการถามกลับ
                if response.get("response_metadata", {}).get("is_clarification"):
                    session_ctx.update({k: v for k, v in intent_result["entities"].items() if v and k != "keywords"})
            
            # 4. แสดงผลและตรวจสอบเบื้องต้น
            display = response.get("display_text", "")
            meta = response.get("response_metadata", {})
            source = "clarify" if meta.get("is_clarification") else ("canned" if meta.get("is_canned") else "llm")
            
            print(f"    {D}[{source}] {display[:100]}...{X}")
            
            # ตรวจสอบความคาดหวังแบบง่าย (Heuristic Check)
            if source == "clarify" and "ระบุ" in display:
                print(f"    {G}✓ Clarification triggered{X}")
            elif "99,580" in display or "2.75" in display or "NLP" in display or "Mango" in display:
                print(f"    {G}✓ Fact Correct{X}")
            elif "ไม่พบข้อมูล" in display or "ขออภัย" in display:
                print(f"    {Y}⚠ Groundedness (No Info){X}")
            elif source == "canned":
                print(f"    {G}✓ Safety/Canned triggered{X}")
            
        print(f"  {'─'*50}")

if __name__ == "__main__":
    run_test()