"""
test_rag.py — AIDA Full Pipeline Test Suite
Path: /Users/aoyrzz/Desktop/AIDA-chatbot/backend/test/test_rag.py
code นี้ใช้ Test-Driven Development (TDD) approach เพื่อทดสอบทั้งระบบ RAG pipeline ตั้งแต่การจำแนกเจตนา การดึงข้อมูลจากฐานความรู้ 
ไปจนถึงการสร้างคำตอบด้วย LLM และการจัดรูปแบบคำตอบ

วิธีรัน:
    python backend/test/test_rag.py               # full suite
    python backend/test/test_rag.py --skip-llm    # ข้าม Section 4+6 (quota หมด)
    python backend/test/test_rag.py --section 3   # รันเฉพาะ section ที่ต้องการ
"""

import sys
import os
import json
import time
import argparse

# ── CLI flags ──────────────────────────────────────
_p = argparse.ArgumentParser(add_help=False)
_p.add_argument("--skip-llm",  action="store_true")
_p.add_argument("--section",   type=int, default=0)
_args, _ = _p.parse_known_args()
SKIP_LLM    = _args.skip_llm
RUN_SECTION = _args.section

# ── Project path ───────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "ai_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "database", "embeddings"))

# ── ANSI ───────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"

# ──────────────────────────────────────────────────
# TEST CASES  (query, expected_intent, expect_retrieval)
# ──────────────────────────────────────────────────
TEST_CASES = [
    # greeting / small_talk
    ("สวัสดีครับ",                               "greeting",        False),
    ("หวัดดีนะ AIDA",                            "greeting",        False),
    ("ขอบคุณมากเลยนะ",                           "small_talk",      False),
    # toxic
    ("มึงโง่มาก ควาย",                           "toxic",           False),
    # out_of_scope / report
    ("ใครชนะบอลโลก 2026",                        "out_of_scope",    False),
    ("ระบบเน็ตล่ม เข้าไม่ได้เลย",                "report_issue",    False),
    # admission
    ("ค่าเทอมปี 1 เท่าไหร่ครับ",                "admission_info",  True),
    ("กู้ กยศ ได้ไหม",                           "admission_info",  True),
    # staff — *** ใช้ tokens check จึงไม่ติด "hi" ใน "Machine" อีกต่อไป ***
    ("อาจารย์ในสาขามีใครบ้าง",                   "staff_info",      True),
    ("ดร. ใครสอนวิชา Machine Learning",          "staff_info",      True),
    # course_desc
    ("ITE301 เรียนเกี่ยวกับอะไรบ้าง",            "course_desc",     True),
    ("วิชา CSC201 สอนอะไร",                      "course_desc",     True),
    # curriculum
    ("ปี 1 เทอม 1 ต้องเรียนวิชาอะไรบ้าง",        "curriculum_info", True),
    ("ขอแผนการเรียนปี 2567 หน่อยได้มั้ย",        "curriculum_info", True),
    ("โครงสร้างหลักสูตร 65 เป็นยังไง",           "curriculum_info", True),
    # coop — *** coop rule ต้องมาก่อน mou rule ***
    ("สหกิจมีบริษัทอะไรบ้าง",                    "coop_intern",     True),
    # career / mou
    ("จบไปทำงานอะไรได้บ้าง เงินเดือนเท่าไหร่",   "career_info",     True),
    ("Huawei เป็น MOU กับสาขาไหม",               "mou_company",     True),
]

# ──────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────

def hdr(t):
    print(f"\n{B}{C}{'='*60}{X}\n{B}{C}  {t}{X}\n{B}{C}{'='*60}{X}")

def sec(t):
    print(f"\n{B}── {t} ──{X}")

def ok(m):   print(f"  {G}✓{X}  {m}")
def fail(m): print(f"  {R}✗{X}  {m}")
def warn(m): print(f"  {Y}⚠{X}  {m}")
def info(m): print(f"  {D}·{X}  {D}{m}{X}")

def chk(cond, label, detail=""):
    s = f"{G}✓{X}" if cond else f"{R}✗{X}"
    print(f"  {s}  {label}  {D}{detail}{X}")
    return cond

def should_run(n):
    return RUN_SECTION == 0 or RUN_SECTION == n

# ──────────────────────────────────────────────────
# SECTION 1 — Import check
# ──────────────────────────────────────────────────

def s1_imports():
    sec("1 · Import check")
    mods = {}
    for name in ["intent_classifier", "rag_handler", "llm_interface", "response_formatter"]:
        try:
            mods[name] = __import__(name)
            ok(f"import {name}")
        except ImportError as e:
            fail(f"import {name}  →  {e}")
            mods[name] = None
    return mods

# ──────────────────────────────────────────────────
# SECTION 2 — Intent Classifier
# ──────────────────────────────────────────────────

def s2_intent(mods):
    sec("2 · Intent Classifier (Zone 1)")
    mod = mods.get("intent_classifier")
    if not mod:
        warn("ข้าม — import ล้มเหลว"); return None

    try:
        clf = mod.ThaiIntentClassifier()
        clf.load()
        ok("load() สำเร็จ")
    except FileNotFoundError as e:
        fail(f"ไม่พบโมเดล: {e}"); return None
    except Exception as e:
        fail(f"load() error: {e}"); return None

    passed = failed = 0
    print(f"\n  {'Query':<44} {'Expected':<20} {'Got':<20} {'OK?':>4}")
    print(f"  {'-'*92}")

    for query, expected, _ in TEST_CASES:
        try:
            r     = clf.predict(query)
            label = r["intent"]["label"]
            conf  = r["intent"]["confidence"]
            disp  = r["intent"].get("display_name", "")
            match = (label == expected)
            sym   = f"{G}✓{X}" if match else f"{Y}~{X}"
            print(f"  {query[:43]:<44} {expected:<20} {label:<20} {sym}")
            if not disp.startswith("[หมวดหมู่:"):
                warn(f"    display_name ผิดรูปแบบ: '{disp}'")
            if match: passed += 1
            else:     failed += 1
        except Exception as e:
            fail(f"  {query[:43]}  →  {e}"); failed += 1

    pct = passed / (passed + failed) * 100 if (passed + failed) else 0
    col = G if pct >= 80 else Y if pct >= 60 else R
    print(f"\n  {col}Intent accuracy: {passed}/{passed+failed}  ({pct:.0f}%){X}")

    # แจ้ง known bugs ถ้ายังเจออยู่
    if failed > 0:
        print()
        warn("Known bugs ใน intent_classifier.py ที่ยังไม่แก้:")
        warn("  Bug1: greeting rule ใช้ substring — 'hi' in 'Machine' = True → แก้เป็น token check")
        warn("  Bug2: mou_company rule อยู่ก่อน coop_intern → 'สหกิจมีบริษัทอะไรบ้าง' ผิด")
        warn("  ดูไฟล์ intent_classifier_fix.py สำหรับ patch ที่แก้แล้ว")

    return clf

# ──────────────────────────────────────────────────
# SECTION 3 — RAG Handler
# ──────────────────────────────────────────────────

def s3_rag(mods, clf):
    sec("3 · RAG Handler (Zone 2)")
    mod = mods.get("rag_handler")
    if not mod:
        warn("ข้าม — import ล้มเหลว"); return None, {}

    try:
        rag = mod.RAGHandler()
        ok("RAGHandler() init สำเร็จ")
    except Exception as e:
        fail(f"init error: {e}"); return None, {}

    # ── 3.2 Skip intents ──
    print()
    print("  [3.2] Skip-retrieval intents → ต้องได้ []")
    for q, label in [("สวัสดีครับ","greeting"),("มึงโง่","toxic"),
                     ("ระบบพัง","report_issue"),("ใครชนะบอลโลก","out_of_scope"),
                     ("ขอบคุณนะ","small_talk")]:
        ir = clf.predict(q) if clf else _dummy_intent(label, "")
        chunks = rag.retrieve(q, ir)
        chk(chunks == [], f"'{label}' → คืน []", f"got {len(chunks)} chunks")

    # ── 3.3 Retrieval intents ──
    print()
    print("  [3.3] Retrieval intents → ต้องได้ chunks > 0")
    ret_store = {}
    for q, label in [("ค่าเทอมเท่าไหร่","admission_info"),
                     ("อาจารย์มีใครบ้าง","staff_info"),
                     ("สหกิจมีบริษัทอะไรบ้าง","coop_intern")]:
        ir = clf.predict(q) if clf else _dummy_intent(label, f"[หมวดหมู่: {label}]")
        t0 = time.perf_counter()
        chunks = rag.retrieve(q, ir)
        ms = (time.perf_counter() - t0) * 1000
        chk(len(chunks) > 0, f"'{label}' → {len(chunks)} chunks  ({ms:.0f}ms)")
        if chunks:
            c = chunks[0]
            chk("text"  in c, "  chunk มี 'text'",  f"keys={list(c.keys())}")
            chk("score" in c, "  chunk มี 'score'", f"keys={list(c.keys())}")
            chk(isinstance(c["text"], str) and len(c["text"]) > 10,
                "  text ไม่ว่าง", f"len={len(c['text'])}")
            chk(isinstance(c["score"], (int, float)),
                "  score เป็น number", f"type={type(c['score']).__name__}")
            ret_store[label] = chunks

    # ── 3.4 Fallback ──
    print()
    print("  [3.4] Fallback — force_category ที่ไม่มีใน KB")
    dummy = _dummy_intent("curriculum_info", "[หมวดหมู่: หมวดที่ไม่มีอยู่จริง XYZ]")
    fb = rag.retrieve("เรียนอะไร", dummy)
    chk(isinstance(fb, list), f"คืน list ไม่ throw", f"got {len(fb)} chunks")

    # ── 3.5 Career KB gap check ──
    print()
    print("  [3.5] Career info KB gap check")
    ir_career = _dummy_intent("career_info", "[หมวดหมู่: ข้อมูลอาชีพหลังเรียนจบ]")
    career_chunks = rag.retrieve("จบไปทำงานอะไร", ir_career)
    if len(career_chunks) == 0:
        warn("career_info ไม่มี chunks ใน KB → แก๊งต้องเพิ่ม data แล้ว re-embed")
    else:
        ok(f"career_info มี {len(career_chunks)} chunks")

    return rag, ret_store

def _dummy_intent(label, display_name):
    return {
        "intent":   {"label": label, "display_name": display_name, "confidence": 1.0},
        "entities": {"curriculum_year":"","year":"","semester":"","course_code":"","keywords":[]},
        "processing_meta": {}
    }

# ──────────────────────────────────────────────────
# SECTION 4 — LLM Interface
# ──────────────────────────────────────────────────

def s4_llm(mods, rag, ret_store):
    sec("4 · LLM Interface (Zone 3)")

    if SKIP_LLM:
        warn("ข้าม — --skip-llm flag (quota หมด หรือต้องการทดสอบเร็ว)")
        return None

    mod = mods.get("llm_interface")
    if not mod:
        warn("ข้าม — import ล้มเหลว"); return None

    try:
        llm = mod.LLMInterface()
        ok("LLMInterface() init สำเร็จ")
    except ValueError as e:
        fail(f"{e}"); warn("ตรวจสอบ GEMINI_API_KEY ใน .env"); return None
    except Exception as e:
        fail(f"init error: {e}"); return None

    # 4.2 entity context
    print()
    print("  [4.2] _build_entity_context()")
    for ent, must in [
        ({"curriculum_year":"2567","year":"1","semester":"2","course_code":"ITE301","keywords":["วิชา"]},
         ["2567","ITE301"]),
        ({}, []),
    ]:
        r = llm._build_entity_context(ent)
        chk(all(v in r for v in must) and isinstance(r, str),
            f"entities={list(ent.keys())} → '{r[:60]}'")

    # 4.3 API call
    print()
    print("  [4.3] API call — 1 query (อาจใช้เวลา 5-15 วิ)")
    test_ir = _dummy_intent("admission_info", "[หมวดหมู่: ค่าเทอมและการเงิน]")
    test_ir["intent"]["confidence"] = 0.98
    test_ir["entities"]["year"] = "1"
    test_chunks = ret_store.get("admission_info", [
        {"text": "[หมวดหมู่: ค่าเทอมและการเงิน]\nค่าเทอมปี 1 ประมาณ 35,000 บาทต่อเทอม", "score": 0.1}
    ])

    t0 = time.perf_counter()
    try:
        resp = llm.generate_response("ค่าเทอมปี 1 เท่าไหร่", test_chunks, test_ir)
        ms   = (time.perf_counter() - t0) * 1000
        chk(resp is not None, f"ได้ response ไม่ใช่ None  [{ms:.0f}ms]")
        if resp:
            for k in ["display_text","speech_text","emotion","response_metadata"]:
                chk(k in resp, f"  มี key '{k}'")
            valid_em = {"Normal","Talking","Happy","Curious","Encouraging"}
            chk(resp.get("emotion") in valid_em,
                f"  emotion valid: '{resp.get('emotion')}'")
            speech = resp.get("speech_text","")
            bad = [c for c in ["*","#","|","\\"] if c in speech]
            chk(not bad, "  speech_text ไม่มีสัญลักษณ์พิเศษ",
                f"พบ: {bad}" if bad else "")
            print()
            info(f"display: {resp['display_text'][:90]}")
            info(f"speech:  {resp['speech_text'][:90]}")
            info(f"emotion: {resp['emotion']}")
    except Exception as e:
        fail(f"generate_response error: {e}")
        return None

    return llm

# ──────────────────────────────────────────────────
# SECTION 5 — Response Formatter
# ──────────────────────────────────────────────────

def s5_formatter(mods):
    sec("5 · Response Formatter (Zone 4)")
    mod = mods.get("response_formatter")
    if not mod:
        warn("ข้าม — import ล้มเหลว"); return

    RF = mod.ResponseFormatter

    # 5.1 canned
    print("  [5.1] handle_no_retrieval() — canned intents")
    for label in ["toxic","greeting","out_of_scope","report_issue"]:
        r = RF.handle_no_retrieval(_dummy_intent(label,""))
        chk(r is not None, f"'{label}' → canned response")
        if r:
            for k in ["display_text","speech_text","emotion","response_metadata"]:
                chk(k in r, f"  มี {k}")
            chk(r.get("response_metadata",{}).get("is_canned") is True,
                "  is_canned=True")

    # 5.2 non-canned → None
    print()
    print("  [5.2] handle_no_retrieval() — non-canned → None")
    for label in ["admission_info","staff_info","curriculum_info","course_desc"]:
        r = RF.handle_no_retrieval(_dummy_intent(label,""))
        chk(r is None, f"'{label}' → None")

    # 5.3 format_output valid
    print()
    print("  [5.3] format_output() — valid LLM response")
    dummy_llm = {
        "display_text": "ค่าเทอมปี 1 ประมาณ 35,000 บาทค่ะ",
        "speech_text":  "ค่าเทอมปี 1 ประมาณ 35,000 บาทค่ะ",
        "emotion":      "Talking",
        "response_metadata": {"data_type":"fact","confidence_score":0.95}
    }
    ir = _dummy_intent("admission_info","")
    ir["entities"]["year"] = "1"
    out = RF.format_output(dummy_llm, ir)
    for k in ["display_text","speech_text","emotion","response_metadata"]:
        chk(k in out, f"  มี {k}")
    chk(out["response_metadata"].get("intent") == "admission_info",
        f"  metadata.intent = '{out['response_metadata'].get('intent')}'")
    chk("entities" in out["response_metadata"], "  metadata.entities ส่งออกด้วย")
    chk(out["emotion"] == "Talking", f"  emotion preserved: '{out['emotion']}'")

    # 5.4 invalid emotion fallback
    print()
    print("  [5.4] format_output() — invalid emotion → Normal")
    valid = {"Normal","Talking","Happy","Curious","Encouraging"}
    for em in ["Angry","Sad","Random","","HAPPY","normal"]:
        dummy_llm["emotion"] = em
        out = RF.format_output(dummy_llm, ir)
        chk(out["emotion"] in valid,
            f"  emotion='{em}' → '{out['emotion']}'")

    # 5.5 None input → default
    print()
    print("  [5.5] format_output() — None input → default")
    out = RF.format_output(None, ir)
    chk(out is not None, "  ไม่ throw")
    chk(len(out.get("display_text","")) > 0, "  display_text ไม่ว่าง")
    chk(out.get("emotion") in {"Normal","Curious"},
        f"  emotion valid: '{out.get('emotion')}'")

# ──────────────────────────────────────────────────
# SECTION 6 — End-to-End
# ──────────────────────────────────────────────────

def s6_e2e(clf, rag, llm, mods):
    sec("6 · End-to-End Pipeline")

    if SKIP_LLM:
        warn("ข้าม — --skip-llm flag")
        return

    mod_rf = mods.get("response_formatter")
    if not all([clf, rag, llm, mod_rf]):
        warn("ข้าม — มี component โหลดไม่สำเร็จ"); return

    RF = mod_rf.ResponseFormatter

    cases = [
        ("สวัสดีครับ",                True,  {"Happy"}),
        ("มึงโง่",                    True,  {"Curious"}),
        ("ค่าเทอมปี 1 เท่าไหร่",     False, {"Normal","Talking","Happy","Curious","Encouraging"}),
        ("จบไปทำงานอะไรได้บ้าง",     False, {"Normal","Talking","Happy","Curious","Encouraging"}),
    ]

    for query, expect_canned, expect_emotions in cases:
        print()
        info(f"Query: {query}")
        t0 = time.perf_counter()
        try:
            ir     = clf.predict(query)
            canned = RF.handle_no_retrieval(ir)
            if canned:
                final = canned
                info("→ Canned response")
            else:
                chunks  = rag.retrieve(query, ir)
                llm_raw = llm.generate_response(query, chunks, ir)
                final   = RF.format_output(llm_raw, ir)

            ms     = (time.perf_counter() - t0) * 1000
            is_can = final.get("response_metadata",{}).get("is_canned", False)
            chk(is_can == expect_canned, f"is_canned={is_can} (expected {expect_canned})")
            chk(final.get("emotion") in expect_emotions,
                f"emotion='{final.get('emotion')}'  [{ms:.0f}ms]")
            chk(len(final.get("display_text","")) > 5,
                f"display_text ({len(final.get('display_text',''))} chars)")
            info(f"  intent: {ir['intent']['label']}  (conf={ir['intent']['confidence']:.2f})")
            info(f"  answer: {final['display_text'][:80]}")
        except Exception as e:
            fail(f"E2E error: {e}")

# ──────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────

def main():
    hdr("AIDA RAG Pipeline — Full Test Suite")
    print(f"{D}  Project root: {PROJECT_ROOT}{X}")
    if SKIP_LLM:
        print(f"{Y}  Mode: --skip-llm (Section 4+6 จะถูกข้าม){X}")
    if RUN_SECTION:
        print(f"{Y}  Mode: --section {RUN_SECTION} (รันเฉพาะ section นี้){X}")
    t0 = time.perf_counter()

    mods = s1_imports()  if should_run(1) else {}

    clf = None
    if should_run(2):
        clf = s2_intent(mods)

    rag, ret_store = (None, {})
    if should_run(3):
        rag, ret_store = s3_rag(mods, clf)

    llm = None
    if should_run(4):
        llm = s4_llm(mods, rag, ret_store)

    if should_run(5):
        s5_formatter(mods)

    if should_run(6):
        s6_e2e(clf, rag, llm, mods)

    total = time.perf_counter() - t0
    print(f"\n{B}{C}{'='*60}{X}")
    print(f"{B}  Total time: {total:.1f}s{X}")
    if SKIP_LLM:
        print(f"{Y}  (LLM sections skipped — รัน full เมื่อ quota reset ที่ 07:00 น.){X}")
    print(f"{B}{C}{'='*60}{X}\n")


if __name__ == "__main__":
    main()