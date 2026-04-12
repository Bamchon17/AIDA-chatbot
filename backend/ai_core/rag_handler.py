"""
rag_handler.py
Path: backend/ai_core/rag_handler.py

สิ่งที่เพิ่มจากเวอร์ชันก่อน:
  - CLARIFICATION_NEEDED  sentinel string
  - CURRICULUM_CLARIFY_RESPONSE  dict พร้อมส่ง Frontend
  - _needs_curriculum_clarification() ตรวจว่าต้องถามปีก่อนไหม
  - retrieve() คืน CLARIFICATION_NEEDED แทน fallback FAISS เมื่อไม่มีปี
"""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.database.embeddings.kb_loader import KnowledgeBaseLoader

# ================================================================
# Intent ที่ไม่ต้องค้นหาข้อมูลจาก Vector DB เลย
# ================================================================
NO_RETRIEVAL_INTENTS = {
    "greeting",
    "small_talk",
    "out_of_scope",
    "report_issue",
    "toxic",
}

# ================================================================
# Clarification constants
# ใช้ตรวจใน pipeline: if chunks is CLARIFICATION_NEEDED → ถามกลับ
# ================================================================
CLARIFICATION_NEEDED = "__CLARIFICATION_NEEDED__"

CURRICULUM_CLARIFY_RESPONSE = {
    "display_text": (
        "หนูอยากตอบให้ตรงหลักสูตรของน้องเลยค่ะ 😊\n"
        "รบกวนบอกหนูด้วยได้ไหมคะว่าน้องอยู่หลักสูตรปีไหน?\n\n"
        "• หลักสูตร ปี 2565\n"
        "• หลักสูตร ปี 2566\n"
        "• หลักสูตร ปี 2567\n"
        "• หลักสูตร ปี 2568"
    ),
    "speech_text": (
        "หนูอยากตอบให้ตรงหลักสูตรของน้องค่ะ "
        "รบกวนบอกหนูด้วยได้ไหมคะว่าน้องอยู่หลักสูตรปีไหน "
        "เช่น หลักสูตรปี 2567 หรือ หลักสูตรปี 2568 คะ"
    ),
    "emotion": "Curious",
    "response_metadata": {
        "intent":           "curriculum_info",
        "data_type":        "logic",
        "confidence_score": 1.0,
        "is_canned":        True,
        "is_clarification": True,
    }
}


class RAGHandler:
    def __init__(self):
        self.kb_loader  = KnowledgeBaseLoader()
        self.index_name = "combined_embedded"
        print("[INFO] Loading RAG Handler (WangchanBERTa Intent Mode)...")
        try:
            self.kb_loader.load_system(self.index_name)
        except AttributeError:
            print("[INFO] load_system() not found — will load on first search()")

    # ─────────────────────────────────────────────
    # PRIVATE: ตรวจว่าต้องถามปีหลักสูตรก่อนไหม
    # ─────────────────────────────────────────────
    def _needs_curriculum_clarification(self, intent_result: dict) -> bool:
        """
        คืน True เมื่อ:
          - label == "curriculum_info"  (ถามแผนการเรียนทั่วไป ไม่ระบุปี)
          - curriculum_year ว่าง  (ไม่มีปีใน entities)
        กรณีที่ผ่าน (คืน False):
          - label == "degreeplan2565/2566/2567/2568"  (ระบุปีในชื่อ intent แล้ว)
          - curriculum_info ที่ user พิมพ์ปีมาด้วย เช่น "แผนการเรียน 2567"
        """
        label    = intent_result.get("intent", {}).get("label", "")
        entities = intent_result.get("entities", {})
        return (
            label == "curriculum_info"
            and not entities.get("curriculum_year", "").strip()
        )

    # ─────────────────────────────────────────────
    # PUBLIC: ค้นหา chunks
    # ─────────────────────────────────────────────
    def retrieve(self, query: str, intent_result: dict, top_k: int = 5):
        """
        ค้นหา chunks จาก Knowledge Base

        Returns:
            []                    — skip (canned intents)
            CLARIFICATION_NEEDED  — ต้องถามปีหลักสูตรก่อน
            list[dict]            — chunks {"text", "score"} ปกติ
        """
        intent_info  = intent_result.get("intent", {})
        label        = intent_info.get("label", "out_of_scope")
        display_name = intent_info.get("display_name", "")

        # ── ด่าน 1: Skip intents ──────────────────────────
        if label in NO_RETRIEVAL_INTENTS:
            print(f"[RAG] Intent '{label}' → skip retrieval")
            return []

        # ── ด่าน 2: Curriculum ไม่มีปี → ถามกลับ ──────────
        if self._needs_curriculum_clarification(intent_result):
            print(f"[RAG] curriculum_info ไม่มีปี → clarification needed")
            return CLARIFICATION_NEEDED

        # curriculum_info มี chunk เยอะต่อปี → เพิ่ม top_k
        if label == "curriculum_info":
            top_k = max(top_k, 15)
            return CLARIFICATION_NEEDED

        # ── ด่าน 3: Filtered vector search ────────────────
        # course_desc: ถ้ามี course_code entity (เช่น AIE455)
        # ให้กรองด้วย exact string match ก่อน แล้วค่อย vector search
        # แก้ปัญหา top_k ไม่เพียงพอเมื่อมี 229 chunks
        entities    = intent_result.get("entities", {})
        course_code = entities.get("course_code", "").strip().upper()

        if label == "course_desc" and course_code:
            print(f"[RAG] course_desc + course_code='{course_code}' → exact pre-filter")
            try:
                raw_chunks = self.kb_loader.chunks or []
                course_chunks = [
                    {"text": c, "score": 0.0}
                    for c in raw_chunks
                    if course_code in c
                ]
                if course_chunks:
                    print(f"[RAG] พบ {len(course_chunks)} chunks ที่มี {course_code}")
                    return course_chunks[:top_k]
                else:
                    print(f"[RAG] ไม่พบ {course_code} ใน KB → fallback vector search")
            except Exception:
                pass

        # course_desc ไม่มี course_code หรือ pre-filter ไม่เจอ → เพิ่ม top_k
        if label == "course_desc":
            top_k = max(top_k, 15)

        force_category = (
            display_name
            if display_name.startswith("[หมวดหมู่:")
            else None
        )

        if force_category:
            print(f"[RAG] Intent '{label}' → Filter: {force_category}")
        else:
            print(f"[RAG] Intent '{label}' → Full search (no filter)")

        try:
            # ── Enrich query ด้วย entities ที่รู้แล้ว ────────────────────────
            # ช่วยให้ vector search rank chunk ที่ตรงรุ่น/แผนขึ้นมาก่อน
            # สำคัญเมื่อ KB เป็นแบบ A (tag แค่ระดับปี ไม่แยก tag รุ่น/แผน)
            enriched_query = query
            if entities.get("generation"):
                enriched_query += f" รุ่น {entities['generation']}"
            if entities.get("plan"):
                enriched_query += f" แผน{entities['plan']}"
            if enriched_query != query:
                print(f"[RAG] enriched query: ...+รุ่น {entities.get('generation','')} แผน{entities.get('plan','')}")

            results = self.kb_loader.search(
                query=enriched_query,
                save_name=self.index_name,
                top_k=top_k,
                force_category=force_category
            )

            # Fallback: กรองแล้วไม่เจอ → full search
            if not results and force_category:
                print(f"[RAG] No results with filter → retrying full search")
                results = self.kb_loader.search(
                    query=enriched_query,
                    save_name=self.index_name,
                    top_k=top_k,
                    force_category=None
                )

            if not results:
                return []

            # isinstance check: ป้องกัน res เป็น string (เช่น raw chunk text)
            # แทนที่จะเป็น dict {"chunk": str, "distance": float}
            formatted = []
            for res in results:
                if isinstance(res, dict):
                    formatted.append({
                        "text":  res.get("chunk", res.get("text", "")),
                        "score": res.get("distance", res.get("score", 0.0))
                    })
                elif isinstance(res, str):
                    formatted.append({"text": res, "score": 0.0})
            return formatted

        except Exception as e:
            print(f"[RAG Error] Retrieval failed: {e}")
            return []