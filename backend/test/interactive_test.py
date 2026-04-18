"""
interactive_test.py — ทดสอบ AIDA pipeline แบบพิมเองทีละคำถาม
Path: /Users/aoyrzz/Desktop/AIDA-chatbot/backend/test/interactive_test.py

วิธีรัน:
    python backend/test/interactive_test.py
    python backend/test/interactive_test.py --verbose   # แสดง chunks ด้วย
"""

import sys, os, re, time, argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "ai_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "database", "embeddings"))

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"
B="\033[1m";  D="\033[2m";  X="\033[0m";  M="\033[95m"


def _parse_bare_answer(query: str, session_ctx: dict) -> dict:
    """
    เมื่อ user ตอบสั้นๆ หลังถูกถามกลับ เช่น "2567", "1/1", "ปกติ"
    พยายามแปลงเป็น entity โดยดูจาก session ว่าตอนนี้รอ entity อะไรอยู่
    """
    q = query.strip()
    extra = {}

    # รอ curriculum_year → ลอง parse ตัวเลขปี
    if not session_ctx.get("curriculum_year"):
        m = re.match(r'^(256[5-9]|6[5-9])$', q)
        if m:
            y = m.group(1)
            extra["curriculum_year"] = "25" + y if len(y) == 2 else y

    # รอ generation → ลอง parse รุ่น
    elif not session_ctx.get("generation"):
        if re.match(r'^1\s*/\s*1$', q):
            extra["generation"] = "1/1"
        elif re.match(r'^1\s*/\s*2$', q):
            extra["generation"] = "1/2"
        elif q == "2":
            extra["generation"] = "2"

    # รอ plan → ลอง parse แผน
    elif not session_ctx.get("plan"):
        if q in ("ปกติ", "แผนปกติ", "normal", "regular"):
            extra["plan"] = "ปกติ"
        elif q in ("สหกิจ", "แผนสหกิจ", "coop", "co-op", "สหกิจศึกษา", "แผนสหกิจศึกษา"):
            extra["plan"] = "สหกิจ"

    return extra


def _merge_session(intent_result: dict, session_ctx: dict, query: str) -> dict:
    """
    Merge session entities เข้า intent_result
    และ override label ถ้า session บ่งชี้ว่าอยู่ใน clarification flow
    """
    if not session_ctx:
        return intent_result

    entities = dict(intent_result["entities"])

    # parse bare answer (เช่น "2567", "1/1", "ปกติ")
    bare = _parse_bare_answer(query, session_ctx)
    entities.update(bare)

    # merge session entities (อย่า overwrite ถ้า entities ปัจจุบันมีค่าแล้ว)
    for k, v in session_ctx.items():
        if v and not entities.get(k):
            entities[k] = v

    intent_result["entities"] = entities

    # ถ้า session มี curriculum_year แต่ label ออกมาผิด → override เป็น curriculum_info
    label = intent_result["intent"]["label"]
    if session_ctx.get("curriculum_year") and label in ("out_of_scope", "greeting", "small_talk", "admission_info"):
        cy = entities.get("curriculum_year", "")
        dn = (f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี{cy}]"
              if cy else "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร]")
        intent_result["intent"]["label"]        = "curriculum_info"
        intent_result["intent"]["display_name"] = dn
        intent_result["intent"]["confidence"]   = 1.0

    return intent_result


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--verbose", action="store_true")
    args, _ = p.parse_known_args()

    print(f"\n{B}{C}══════════════════════════════════════════{X}")
    print(f"{B}{C}  AIDA Interactive Test (with session){X}")
    print(f"{B}{C}══════════════════════════════════════════{X}")
    print(f"{D}  พิมคำถามแล้วกด Enter{X}")
    print(f"{D}  'clear' = ล้าง session | 'quit' = ออก{X}\n")

    print(f"{D}กำลังโหลด pipeline...{X}")
    try:
        import intent_classifier  as ic_mod
        import rag_handler        as rh_mod
        import llm_interface      as li_mod
        import response_formatter as rf_mod
        from rag_handler import CLARIFICATION_NEEDED

        clf = ic_mod.ThaiIntentClassifier()
        clf.load()
        rag = rh_mod.RAGHandler()
        llm = li_mod.LLMInterface()
        RF  = rf_mod.ResponseFormatter
        print(f"{G}✓ พร้อมแล้ว!{X}\n")
    except Exception as e:
        print(f"{R}✗ โหลดไม่ได้: {e}{X}")
        return

    session_ctx = {}   # จำ entities ข้ามรอบสำหรับ 3-step clarification

    while True:
        try:
            query = input(f"{B}คำถาม:{X} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{D}ออกจากโปรแกรม{X}")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print(f"{D}ออกจากโปรแกรม{X}")
            break
        if query.lower() == "clear":
            session_ctx = {}
            print(f"{Y}✓ ล้าง session แล้ว{X}\n")
            continue

        t0 = time.perf_counter()

        # ── Zone 1: Intent ────────────────────────────────────────────────
        intent_result = clf.predict(query)

        # ── Merge session context ─────────────────────────────────────────
        intent_result = _merge_session(intent_result, session_ctx, query)

        # ── Fix display_name ให้มีปีเสมอเมื่อ curriculum_info + มี curriculum_year ──
        # เพราะ clf.predict("แผนปกติ") ไม่รู้ปี → display_name ไม่มีปี
        # → force_category ใน rag_handler จะไม่ตรงกับ KB tag ที่มีปีต่อท้าย
        if intent_result["intent"]["label"] == "curriculum_info":
            cy = intent_result["entities"].get("curriculum_year", "")
            if cy:
                intent_result["intent"]["display_name"] = (
                    f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี{cy}]"
                )

        intent_info = intent_result["intent"]
        entities    = intent_result["entities"]

        print(f"\n{D}{'─'*46}{X}")
        print(f"  {M}Intent:{X}  {B}{intent_info['label']}{X}  "
              f"({intent_info['confidence']:.2f})  "
              f"{D}{intent_info['display_name']}{X}")

        # แสดง entities ที่พบ
        found_ents = {k: v for k, v in entities.items() if v and k != "keywords"}
        if found_ents:
            print(f"  {M}Entities:{X} {found_ents}")

        # แสดง session ถ้ามี
        if session_ctx:
            print(f"  {D}Session:  {session_ctx}{X}")

        # ── Zone 4 pre-check (canned + clarification) ─────────────────────
        early = RF.handle_no_retrieval(intent_result)
        if early:
            ms   = (time.perf_counter() - t0) * 1000
            meta = early.get("response_metadata", {})
            tag  = "clarify" if meta.get("is_clarification") else "canned"
            step = meta.get("clarification_step", "")
            print(f"  {M}Source:{X}   {Y}{tag}{X}"
                  + (f"  step={step}" if step else "")
                  + f"  [{ms:.0f}ms]")
            print(f"\n  {G}display:{X} {early['display_text']}")
            print(f"  {C}speech: {X}{D}{early['speech_text']}{X}")
            print(f"  {M}emotion:{X}  {early['emotion']}\n")

            if meta.get("is_clarification"):
                # บันทึก entities ที่สะสมได้ลง session
                session_ctx.update({k: v for k, v in entities.items()
                                    if v and k != "keywords"})
            else:
                # canned ปกติ → clear session
                session_ctx = {}
            continue

        # ── Zone 2: RAG ───────────────────────────────────────────────────
        chunks = rag.retrieve(query, intent_result)

        if chunks is CLARIFICATION_NEEDED:
            print(f"  {Y}[CLARIFICATION_NEEDED — ตรวจสอบ handle_no_retrieval]{X}\n")
            continue

        if args.verbose and chunks:
            print(f"  {D}chunks: {len(chunks)}{X}")
            for i, c in enumerate(chunks[:3], 1):
                preview = c["text"].replace("\n", " ")[:90]
                print(f"  {D}  [{i}] {preview}…{X}")

        # ── Zone 3: LLM ───────────────────────────────────────────────────
        llm_raw = llm.generate_response(query, chunks, intent_result)

        # ── Zone 4: Format ────────────────────────────────────────────────
        final = RF.format_output(llm_raw, intent_result)

        ms   = (time.perf_counter() - t0) * 1000
        meta = final.get("response_metadata", {})
        print(f"  {M}Source:{X}   llm  [{ms:.0f}ms]  "
              f"data_type={meta.get('data_type','')}  "
              f"chunks={len(chunks)}")
        print(f"\n  {G}display:{X} {final['display_text']}")
        print(f"  {C}speech: {X}{D}{final['speech_text'][:120]}{X}")
        print(f"  {M}emotion:{X}  {final['emotion']}\n")

        # ตอบสำเร็จ → clear session
        session_ctx = {}


if __name__ == "__main__":
    main()