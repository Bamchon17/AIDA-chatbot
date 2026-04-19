"""
test_llm_output.py — LLM Output Quality Test (ครอบคลุมทุกหมวด)
Path: /Users/aoyrzz/Desktop/AIDA-chatbot/backend/test/test_llm_output.py

วิธีรัน:
    python backend/test/test_llm_output.py                      # ทุกหมวด
    python backend/test/test_llm_output.py --category fees      # เฉพาะหมวด
    python backend/test/test_llm_output.py --save-report        # บันทึก JSON report
    python backend/test/test_llm_output.py --verbose            # แสดง chunks ด้วย

--category: fees | staff | courses | degreeplan | coop | mou | career | greeting | toxic | oob | clarify
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "ai_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "database", "embeddings"))

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"
B="\033[1m";  D="\033[2m";  X="\033[0m";  M="\033[95m"

# ═════════════════════════════════════════════════════════════════════════════
# TEST CASES
# หมายเหตุ emotion_in:
#   - ถ้า KB มีข้อมูลครบ LLM จะตอบ Talking
#   - ถ้า KB ไม่มีข้อมูล LLM จะตอบ Curious (ถูกต้องตามระบบ)
#   - จึงใส่ ["Talking", "Curious"] สำหรับ query ที่ขึ้นกับความสมบูรณ์ของ KB
# ═════════════════════════════════════════════════════════════════════════════
TEST_CASES = [

    # ── ค่าเทอมและการเงิน ─────────────────────────────────────────────────────
    ("fees", "ค่าเทอมปี 1 เท่าไหร่ครับ", [
        {"type": "not_hallucinate", "desc": "ต้องอ้างจาก context ไม่ใช่ตัวเลขสุ่ม"},
        {"type": "no_symbols",      "desc": "speech_text ไม่มี * # bullet"},
        {"type": "emotion_in",      "desc": "emotion ถูกต้อง",
         "values": ["Talking"]},
        {"type": "data_fact",       "desc": "data_type ควรเป็น fact"},
    ]),
    # [Stress] การบวกเลขจากหลาย chunk — ต้องใช้ข้อมูลจาก context
    ("fees", "ปี 1 ทั้งปีต้องเตรียมเงินกี่บาท", [
        {"type": "not_hallucinate", "desc": "[Stress] ต้องบวกเลขจาก context (1/1 + 1/2)"},
        {"type": "no_symbols",      "desc": "speech_text สะอาด"},
        {"type": "emotion_in",      "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),
    # [Stress] ข้อมูลอาจไม่มีใน KB → ต้องไม่ hallucinate
    ("fees", "ภาคฤดูร้อนมีค่าใช้จ่ายไหม", [
        {"type": "not_empty",  "desc": "[Stress] เช็กว่า KB มีข้อมูลซัมเมอร์ไหม"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── อาจารย์และบุคลากร ─────────────────────────────────────────────────────
    ("staff", "ในสาขามีอาจารย์กี่คน และมีใครบ้าง", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text ไม่มีสัญลักษณ์"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking"]},
    ]),
    ("staff", "ดร. ท่านไหนเชี่ยวชาญด้าน AI บ้าง", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text ไม่มีสัญลักษณ์"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── รายวิชา ───────────────────────────────────────────────────────────────
    # Existence Test  : AIE455 มีใน KB จริง → ต้องดึงเจอ
    # Groundedness Test: ITE301 ไม่มีใน KB → ต้องตอบ Curious ห้าม Hallucinate
    # Semantic Test   : ถามด้วยเนื้อหา ไม่ใช่รหัส → ทดสอบ vector search จริง
    ("courses", "วิชา AIE455 สอนเรื่องอะไร", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text ไม่มีสัญลักษณ์"},
        {"type": "emotion_in", "desc": "[Existence Test] AIE455 มีใน KB → ต้องได้ Talking",
         "values": ["Talking"]},
        {"type": "data_fact",  "desc": "[Existence Test] data_type ต้องเป็น fact"},
    ]),
    ("courses", "ITE301 เรียนเกี่ยวกับอะไรบ้าง", [
        {"type": "not_empty",  "desc": "ต้องตอบมา (ยอมรับว่าไม่รู้ก็ถือว่าตอบ)"},
        {"type": "no_symbols", "desc": "speech_text ไม่มีสัญลักษณ์"},
        {"type": "emotion_in", "desc": "[Groundedness Test] ITE301 ไม่มีใน KB → Curious ห้าม Hallucinate",
         "values": ["Curious"]},
    ]),
    # [Semantic Stress] ถามด้วยเนื้อหา ไม่มีรหัสวิชา → ทดสอบ vector search
    ("courses", "อยากเรียนเรื่อง Prompt Engineering ต้องลงวิชาอะไร", [
        {"type": "not_empty",  "desc": "[Semantic] ต้องตอบมา (ควรเจอ AIE455 หรือ NLP)"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),
    ("courses", "วิชา AIE121 เรียนเกี่ยวกับอะไร", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text ต้องสะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── แผนการเรียน — ระบุปี ─────────────────────────────────────────────────
    ("degreeplan", "แผนการเรียนปี 2567 ปี 1 เทอม 1 ต้องเรียนอะไรบ้าง", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text ไม่มีสัญลักษณ์"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),
    # [Stress] เปรียบเทียบ 2 path — ต้องดึง chunk ทั้งสองมาตอบ
    ("degreeplan", "แผนปกติกับแผนสหกิจของปี 2567 ต่างกันยังไง", [
        {"type": "not_empty",  "desc": "[Stress] ต้องบอกความต่างของรายวิชาหรือหน่วยกิต"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── แผนการเรียน — ถามกลับ 3 ขั้น ────────────────────────────────────────
    # Step 1: ไม่มีปี → ต้องถามปี
    ("clarify", "ปี 1 เทอม 1 ต้องเรียนวิชาอะไรบ้าง", [
        {"type": "is_clarify",  "desc": "[Step1] ต้องถามกลับ"},
        {"type": "not_empty",   "desc": "มี display_text"},
        {"type": "clarify_step","desc": "[Step1] clarification_step ต้องเป็น year",
         "value": "year"},
        {"type": "emotion_in",  "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),
    ("clarify", "แผนการเรียนเป็นยังไง", [
        {"type": "is_clarify",  "desc": "[Step1] ต้องถามกลับ"},
        {"type": "not_empty",   "desc": "มี display_text"},
        {"type": "clarify_step","desc": "[Step1] clarification_step ต้องเป็น year",
         "value": "year"},
        {"type": "emotion_in",  "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),
    # Step 2: มีปีแล้ว ไม่มีรุ่น → ต้องถามรุ่น
    ("clarify", "แผนการเรียนปี 2567 ปี 1 เทอม 1 มีอะไรบ้าง", [
        {"type": "is_clarify",  "desc": "[Step2] มีปีแต่ไม่มีรุ่น → ต้องถามรุ่น"},
        {"type": "not_empty",   "desc": "มี display_text"},
        {"type": "clarify_step","desc": "[Step2] clarification_step ต้องเป็น generation",
         "value": "generation"},
        {"type": "emotion_in",  "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),
    # Step 3: มีปี+รุ่น ไม่มีแผน → ต้องถามแผน
    ("clarify", "แผนการเรียนปี 2567 รุ่น 1/1 มีวิชาอะไรบ้าง", [
        {"type": "is_clarify",  "desc": "[Step3] มีปี+รุ่นแต่ไม่มีแผน → ต้องถามแผน"},
        {"type": "not_empty",   "desc": "มี display_text"},
        {"type": "clarify_step","desc": "[Step3] clarification_step ต้องเป็น plan",
         "value": "plan"},
        {"type": "emotion_in",  "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),

    # ── สหกิจศึกษา ────────────────────────────────────────────────────────────
    ("coop", "สหกิจศึกษาต้องมีเกรดเฉลี่ยเท่าไหร่", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text ไม่มีสัญลักษณ์"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking"]},
        {"type": "data_fact",  "desc": "data_type ควรเป็น fact"},
    ]),
    # [Stress] ถามเงื่อนไขที่ซับซ้อน — ต้อง reason จาก context
    ("coop", "ถ้าเกรดเฉลี่ยไม่ถึง 2.75 จะฝึกงานได้ไหม", [
        {"type": "not_empty",  "desc": "[Stress] ต้องตอบตามกฎ KB (อาจไปฝึกงานปกติแทน)"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),
    # [Stress] ต้อง cross-intent — ดึงข้อมูล MOU มาตอบเรื่อง coop
    ("coop", "ฝึกงานที่ไหนได้บ้าง มีบริษัทแนะนำไหม", [
        {"type": "not_empty",  "desc": "[Stress] ควรดึงรายชื่อบริษัท MOU มาตอบ"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── บริษัท MOU ────────────────────────────────────────────────────────────
    ("mou", "Huawei เป็น MOU กับสาขาไหม", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking"]},
        {"type": "data_fact",  "desc": "data_type ควรเป็น fact"},
    ]),
    # [Stress] ถามรายละเอียดบริษัท — ทดสอบ chunk ว่ามีเนื้อหาพอไหม
    ("mou", "บริษัท Mango Consultant ทำเกี่ยวกับอะไร", [
        {"type": "not_empty",  "desc": "[Stress] ต้องดึงรายละเอียดบริษัทจาก KB"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
        {"type": "data_fact",  "desc": "data_type ควรเป็น fact"},
    ]),
    # [Semantic Stress] ไม่มีชื่อบริษัท → ทดสอบ semantic search
    ("mou", "มี MOU กับบริษัทที่ทำเรื่อง Robot ไหม", [
        {"type": "not_empty",  "desc": "[Semantic Stress] เช็ก semantic search ใน MOU"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── อาชีพหลังจบ ───────────────────────────────────────────────────────────
    ("career", "เรียนจบ AI & Data Science ทำงานอะไรได้บ้าง", [
        {"type": "not_empty",  "desc": "ต้องตอบมา"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),
    # [Smart Stress] ต้อง cross-intent (career + courses) — โชว์ความฉลาด
    ("career", "อยากเป็น Data Scientist ต้องตั้งใจเรียนวิชาไหนเป็นพิเศษ", [
        {"type": "not_empty",  "desc": "[Smart Stress] ควรดึง career + courses มาผสมตอบ"},
        {"type": "no_symbols", "desc": "speech_text สะอาด"},
        {"type": "emotion_in", "desc": "emotion ถูกต้อง",
         "values": ["Talking", "Curious"]},
    ]),

    # ── Canned: Greeting ──────────────────────────────────────────────────────
    ("greeting", "สวัสดีครับ", [
        {"type": "is_canned",  "desc": "ต้องเป็น canned ไม่ผ่าน LLM"},
        {"type": "emotion_in", "desc": "emotion ต้องเป็น Normal",
         "values": ["Normal"]},
    ]),
    ("greeting", "หวัดดีนะ", [
        {"type": "is_canned",  "desc": "ต้องเป็น canned"},
        {"type": "emotion_in", "desc": "emotion ต้องเป็น Normal",
         "values": ["Normal"]},
    ]),

    # ── Canned: Toxic ─────────────────────────────────────────────────────────
    ("toxic", "มึงโง่มาก", [
        {"type": "is_canned",  "desc": "ต้องเป็น canned บล็อกทันที"},
        {"type": "emotion_in", "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),

    # ── Canned: Out of scope ──────────────────────────────────────────────────
    ("oob", "ใครชนะบอลโลก 2026", [
        {"type": "is_canned",  "desc": "ต้องเป็น canned"},
        {"type": "emotion_in", "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),
    ("oob", "ราคาหุ้น NVDA วันนี้เท่าไหร่", [
        {"type": "is_canned",  "desc": "ต้องเป็น canned"},
        {"type": "emotion_in", "desc": "emotion ต้องเป็น Curious",
         "values": ["Curious"]},
    ]),
]

CATEGORY_LABELS = {
    "fees":       "ค่าเทอมและการเงิน",
    "staff":      "อาจารย์และบุคลากร",
    "courses":    "รายวิชา",
    "degreeplan": "แผนการเรียน (ระบุปี)",
    "clarify":    "แผนการเรียน (3-step clarification)",
    "coop":       "สหกิจศึกษา",
    "mou":        "บริษัท MOU",
    "career":     "อาชีพหลังจบ",
    "greeting":   "ทักทาย (canned)",
    "toxic":      "คำไม่สุภาพ (canned)",
    "oob":        "นอกขอบเขต (canned)",
}

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def hdr(t):
    print(f"\n{B}{C}{'═'*64}{X}\n{B}{C}  {t}{X}\n{B}{C}{'═'*64}{X}")

def sec(t):
    print(f"\n{B}{M}▶  {t}{X}")

def ok(m):   print(f"    {G}✓{X}  {m}")
def fail(m): print(f"    {R}✗{X}  {m}")
def info(m): print(f"    {D}  {m}{X}")


def run_checks(response: dict, checks: list) -> tuple[int, int]:
    passed = failed = 0
    meta = response.get("response_metadata", {})

    for chk in checks:
        t = chk["type"]

        if t == "is_canned":
            result = meta.get("is_canned", False) and not meta.get("is_clarification", False)

        elif t == "is_clarify":
            result = meta.get("is_clarification", False)

        elif t == "clarify_step":
            step   = meta.get("clarification_step", "")
            result = step == chk.get("value", "")
            chk    = dict(chk, desc=f"{chk['desc']}  (got '{step}')")

        elif t == "not_empty":
            result = bool(response.get("display_text", "").strip())

        elif t == "no_symbols":
            speech = response.get("speech_text", "")
            bad    = [c for c in ["*", "#", "|", "\\", "_", "```"] if c in speech]
            result = len(bad) == 0
            chk    = dict(chk, desc=f"{chk['desc']}  {'clean' if result else f'พบ: {bad}'}")

        elif t == "emotion_in":
            em     = response.get("emotion", "")
            result = em in chk["values"]
            chk    = dict(chk, desc=f"{chk['desc']}  (got '{em}', expect {chk['values']})")

        elif t == "data_fact":
            dt     = meta.get("data_type", "")
            result = dt == "fact"
            chk    = dict(chk, desc=f"{chk['desc']}  (got '{dt}')")

        elif t == "not_hallucinate":
            dt     = meta.get("data_type", "")
            result = bool(response.get("display_text", "")) and dt in ("fact", "logic")

        else:
            result = True

        if result:
            ok(chk["desc"]); passed += 1
        else:
            fail(chk["desc"]); failed += 1

    return passed, failed


def load_components():
    try:
        import intent_classifier  as ic_mod
        import rag_handler        as rh_mod
        import llm_interface      as li_mod
        import response_formatter as rf_mod
        print(f"  {G}✓{X}  import ครบทุก module")
    except ImportError as e:
        print(f"  {R}✗{X}  import ล้มเหลว: {e}")
        return None

    try:
        clf = ic_mod.ThaiIntentClassifier()
        clf.load()
    except Exception as e:
        print(f"  {R}✗{X}  Intent classifier: {e}")
        return None

    try:
        rag = rh_mod.RAGHandler()
    except Exception as e:
        print(f"  {R}✗{X}  RAGHandler: {e}")
        return None

    try:
        llm = li_mod.LLMInterface()
    except ValueError as e:
        print(f"  {R}✗{X}  LLMInterface: {e}")
        return None

    return clf, rag, llm, rf_mod.ResponseFormatter


def run_single(query, clf, rag, llm, RF, verbose=False) -> tuple[dict, float]:
    t0 = time.perf_counter()

    intent_result = clf.predict(query)

    # Zone 4 pre-check: canned + clarification
    early = RF.handle_no_retrieval(intent_result)
    if early:
        return early, (time.perf_counter() - t0) * 1000

    chunks = rag.retrieve(query, intent_result)

    # Guard: ถ้า RAG คืน CLARIFICATION_NEEDED (sentinel string) → ตอบถามกลับ
    # ป้องกัน llm_interface รับ string แล้ว enumerate ตัวอักษรแทน chunk
    try:
        from rag_handler import CLARIFICATION_NEEDED, CURRICULUM_CLARIFY_RESPONSE
        if chunks is CLARIFICATION_NEEDED:
            return CURRICULUM_CLARIFY_RESPONSE, (time.perf_counter() - t0) * 1000
    except ImportError:
        pass

    if verbose and isinstance(chunks, list) and chunks:
        print(f"    {D}chunks: {len(chunks)}{X}")
        for i, c in enumerate(chunks[:2], 1):
            preview = c["text"].replace("\n", " ")[:80]
            print(f"    {D}  [{i}] {preview}…{X}")

    llm_raw = llm.generate_response(query, chunks, intent_result)
    final   = RF.format_output(llm_raw, intent_result)
    return final, (time.perf_counter() - t0) * 1000

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--category",    default="all")
    p.add_argument("--save-report", action="store_true")
    p.add_argument("--verbose",     action="store_true")
    args, _ = p.parse_known_args()

    hdr("AIDA LLM Output Quality Test — 3 Emotions Edition")
    print(f"{D}  วันที่: {datetime.now().strftime('%Y-%m-%d %H:%M')}{X}")
    print(f"{D}  Emotions: Normal | Talking | Curious{X}")

    print()
    components = load_components()
    if not components:
        return
    clf, rag, llm, RF = components

    cases = TEST_CASES
    if args.category != "all":
        cases = [(c, q, chks) for c, q, chks in TEST_CASES if c == args.category]
        if not cases:
            print(f"{R}ไม่พบ category '{args.category}'{X}")
            print(f"ใช้ได้: {list(CATEGORY_LABELS.keys())}")
            return

    report      = []
    total_p = total_f = 0
    current_cat = None

    for cat, query, checks in cases:
        if cat != current_cat:
            current_cat = cat
            sec(CATEGORY_LABELS.get(cat, cat))

        print(f"\n  {B}Q:{X} {query}")

        try:
            response, ms = run_single(query, clf, rag, llm, RF, verbose=args.verbose)

            display = response.get("display_text", "")
            speech  = response.get("speech_text",  "")
            emotion = response.get("emotion",       "")
            meta    = response.get("response_metadata", {})
            dt      = meta.get("data_type", "")
            is_can  = meta.get("is_canned", False)
            is_clar = meta.get("is_clarification", False)
            tag     = "clarify" if is_clar else ("canned" if is_can else "llm")

            print(f"  {D}[{ms:.0f}ms | emotion={emotion} | type={dt} | source={tag}]{X}")
            print(f"  {G if display else R}display:{X} {display[:120]}{'…' if len(display)>120 else ''}")
            print(f"  {C}speech: {X}{D}{speech[:100]}{'…' if len(speech)>100 else ''}{X}")

            p_cnt, f_cnt = run_checks(response, checks)
            total_p += p_cnt
            total_f += f_cnt

            report.append({
                "category":    cat,
                "query":       query,
                "passed":      p_cnt,
                "failed":      f_cnt,
                "ms":          round(ms, 1),
                "emotion":     emotion,
                "data_type":   dt,
                "source":      tag,
                "display_text": display,
                "speech_text":  speech,
            })

        except Exception as e:
            fail(f"Pipeline error: {e}")
            total_f += 1
            report.append({"category": cat, "query": query,
                           "passed": 0, "failed": 1, "error": str(e)})

    # ── Summary ───────────────────────────────────────────────────────────────
    total = total_p + total_f
    pct   = total_p / total * 100 if total else 0
    col   = G if pct >= 90 else Y if pct >= 75 else R

    hdr("สรุปผล")
    print(f"  Checks ผ่าน  : {col}{total_p}/{total}  ({pct:.0f}%){X}")
    print(f"  Queries ทดสอบ: {len(report)}")

    by_cat = {}
    for r in report:
        c = r["category"]
        by_cat.setdefault(c, {"p": 0, "f": 0, "q": 0})
        by_cat[c]["p"] += r.get("passed", 0)
        by_cat[c]["f"] += r.get("failed", 0)
        by_cat[c]["q"] += 1

    print()
    print(f"  {'หมวด':<36} {'Q':>3}  {'Checks':>8}  {'%':>5}")
    print(f"  {'─'*58}")
    for cat, v in by_cat.items():
        label = CATEGORY_LABELS.get(cat, cat)
        tot   = v["p"] + v["f"]
        pc    = v["p"] / tot * 100 if tot else 0
        col2  = G if pc >= 90 else Y if pc >= 75 else R
        print(f"  {label:<36} {v['q']:>3}  {col2}{v['p']}/{tot}{X}{'':>5}{col2}{pc:.0f}%{X}")

    # KB gap reminder
    print(f"\n  {Y}KB gaps ที่แก๊งต้องเพิ่ม (จะทำให้ Curious → Talking):{X}")
    print(f"  {D}  · รหัสวิชา ITE301 ยังไม่มีใน KB{X}")
    print(f"  {D}  · แผนการเรียน 2567 ปี1เทอม1 ข้อมูลไม่ครบ{X}")
    print(f"  {D}  · ยอดรวมบริษัท MOU ยังไม่มีใน KB{X}")

    if args.save_report:
        out_dir = os.path.join(PROJECT_ROOT, "backend", "test", "reports")
        os.makedirs(out_dir, exist_ok=True)
        fname   = os.path.join(out_dir, f"llm_output_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp":    datetime.now().isoformat(),
                "total_pass":   total_p,
                "total_fail":   total_f,
                "accuracy_pct": round(pct, 1),
                "cases":        report,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n  {G}✓{X}  บันทึก report: {fname}")

    print()


if __name__ == "__main__":
    main()