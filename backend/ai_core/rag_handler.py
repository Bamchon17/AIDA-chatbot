"""
rag_handler.py — Final Version
แก้ไข:
  - เพิ่ม _direct_curriculum_search: ค้นหา chunk ตรงจาก KB ไม่พึ่ง FAISS
  - Soft Ranking: Boost score แทน Hard Filter
  - Cross-search: MOU↔staff, coop↔MOU
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.database.embeddings.kb_loader import KnowledgeBaseLoader

NO_RETRIEVAL_INTENTS = {"greeting","small_talk","out_of_scope","report_issue","toxic"}
CLARIFICATION_NEEDED = "__CLARIFICATION_NEEDED__"

CURRICULUM_CLARIFY_RESPONSE = {
    "display_text": (
        "หนูอยากตอบให้ตรงหลักสูตรของน้องเลยค่ะ 😊\n"
        "รบกวนบอกหนูด้วยได้ไหมคะว่าน้องอยู่หลักสูตรปีไหน?\n\n"
        "• หลักสูตร ปี 2565\n• หลักสูตร ปี 2566\n• หลักสูตร ปี 2567\n• หลักสูตร ปี 2568"
    ),
    "speech_text": (
        "หนูอยากตอบให้ตรงหลักสูตรของน้องค่ะ "
        "รบกวนบอกหนูด้วยได้ไหมคะว่าน้องอยู่หลักสูตรปีไหน "
        "เช่น หลักสูตรปี 2567 หรือ หลักสูตรปี 2568 คะ"
    ),
    "emotion": "Curious",
    "response_metadata": {
        "intent":"curriculum_info","data_type":"logic",
        "confidence_score":1.0,"is_canned":True,"is_clarification":True,
    }
}


class RAGHandler:
    def __init__(self):
        self.kb_loader  = KnowledgeBaseLoader()
        self.index_name = "combined_embedded"
        print("[INFO] Loading RAG Handler...")
        try:
            self.kb_loader.load_system(self.index_name)
        except AttributeError:
            print("[INFO] load_system() not found — will load on first search()")

    def _needs_curriculum_clarification(self, intent_result: dict) -> bool:
        label    = intent_result.get("intent",{}).get("label","")
        entities = intent_result.get("entities",{})
        return label == "curriculum_info" and not entities.get("curriculum_year","").strip()

    def _direct_curriculum_search(self, entities: dict, category: str) -> dict | None:
        """
        ค้นหา chunk โดยใช้ exact header match — ไม่พึ่ง FAISS เลย
        คืน {"text": str, "score": 999.0} เมื่อเจอ หรือ None
        """
        gen  = entities.get("generation","")
        plan = entities.get("plan","")
        year = entities.get("year","")
        sem  = entities.get("semester","")

        if not (gen and plan and year and sem and sem != "summer"):
            return None

        raw_chunks = self.kb_loader.chunks or []
        for chunk in raw_chunks:
            if category not in chunk:            continue
            if f"## ปี {year}" not in chunk:     continue
            if f"ภาคการศึกษาที่ {sem}" not in chunk: continue
            if f"รุ่น {gen}" not in chunk:       continue
            if f"แผน{plan}" not in chunk:        continue
            print(f"[RAG] _direct_search → พบ chunk ตรงเป๊ะ (ปี{year} เทอม{sem} รุ่น{gen} แผน{plan})")
            return {"text": chunk, "score": 999.0}

        print(f"[RAG] _direct_search → ไม่พบ → fallback FAISS")
        return None

    def _rerank_curriculum(self, chunks: list, entities: dict) -> list:
        """
        Soft Ranking: Boost คะแนนมหาศาลให้ chunk ที่ตรง ไม่ลบ chunk ทิ้ง
        ลบช่องว่างก่อนเช็ก ป้องกัน "รุ่น 1 / 1" vs "รุ่น1/1"
        """
        gen  = str(entities.get("generation","")).strip()
        plan = str(entities.get("plan","")).strip()
        year = str(entities.get("year","")).strip()
        sem  = str(entities.get("semester","")).strip()

        for item in chunks:
            text = item.get("text","").replace(" ","")
            boost = 0.0
            if gen:
                if f"รุ่น{gen}" in text:  boost += 20.0
                elif f"({gen})" in text:  boost += 10.0
            if plan and f"แผน{plan}" in text:   boost += 20.0
            if year and f"##ปี{year}" in text:  boost += 10.0
            if sem:
                if sem == "summer":
                    if any(w in text for w in ["ฤดูร้อน","Summer"]): boost += 10.0
                else:
                    if f"เทอม{sem}" in text or f"ภาคการศึกษาที่{sem}" in text:
                        boost += 10.0
            # score = max(existing, 0) + boost ป้องกัน FAISS distance ลบลด boost
            item["score"] = max(item.get("score", 0.0), 0.0) + boost

        ranked = sorted(chunks, key=lambda x: x.get("score",0.0), reverse=True)
        if ranked:
            preview = ranked[0].get("text","")[:60].replace("\n"," ")
            print(f"[RAG] _rerank_curriculum → top={ranked[0].get('score',0):.1f} preview={preview}...")
        return ranked

    def retrieve(self, query: str, intent_result: dict, top_k: int = 5):
        intent_info  = intent_result.get("intent",{})
        label        = intent_info.get("label","out_of_scope")
        display_name = intent_info.get("display_name","")

        if label in NO_RETRIEVAL_INTENTS:
            print(f"[RAG] Intent '{label}' → skip retrieval")
            return []

        if self._needs_curriculum_clarification(intent_result):
            print(f"[RAG] curriculum_info ไม่มีปี → clarification needed")
            return CLARIFICATION_NEEDED

        if label == "curriculum_info": top_k = max(top_k, 30)
        if label == "staff_info":      top_k = max(top_k, 10)
        if label == "course_desc":     top_k = max(top_k, 20)
        if label == "admission_info":  top_k = max(top_k, 10)  # เพิ่มเพื่อให้เจอ chunk ยอดรวม

        entities    = intent_result.get("entities",{})
        course_code = entities.get("course_code","").strip().upper()

        # Exact pre-filter สำหรับรหัสวิชา
        if label == "course_desc" and course_code:
            print(f"[RAG] course_desc + course_code='{course_code}' → exact pre-filter")
            try:
                raw_chunks = self.kb_loader.chunks or []
                cc = [{"text":c,"score":10.0} for c in raw_chunks if course_code in c]
                if cc:
                    print(f"[RAG] พบ {len(cc)} chunks ที่มี {course_code}")
                    desc = [c for c in cc if "คำอธิบาย" in c["text"] or "หมวดหมู่: รายวิชา" in c["text"]]
                    plan = [c for c in cc if c not in desc]
                    return (desc + plan)[:top_k]
                print(f"[RAG] ไม่พบ {course_code} → fallback vector search")
            except Exception: pass

        force_category = display_name if display_name.startswith("[หมวดหมู่:") else None

        if force_category: print(f"[RAG] Intent '{label}' → Filter: {force_category}")
        else:              print(f"[RAG] Intent '{label}' → Full search (no filter)")

        try:
            enriched_query = query
            if entities.get("generation"): enriched_query += f" รุ่น {entities['generation']}"
            if entities.get("plan"):       enriched_query += f" แผน{entities['plan']}"
            if entities.get("semester"):
                s = entities["semester"]
                enriched_query += " ภาคฤดูร้อน Summer" if s=="summer" else f" เทอม {s}"
            if entities.get("year"):       enriched_query += f" ชั้นปีที่ {entities['year']}"
            if enriched_query != query:
                print(f"[RAG] enriched query: ...+รุ่น {entities.get('generation','')} แผน{entities.get('plan','')}")

            results = self.kb_loader.search(
                query=enriched_query, save_name=self.index_name,
                top_k=top_k, force_category=force_category
            )

            # Direct search: curriculum ที่รู้ entities ครบ — ค้นตรงจาก KB
            if label == "curriculum_info" and force_category:
                direct = self._direct_curriculum_search(entities, force_category)
                if direct:
                    results = [{"distance":0.0,"chunk":direct["text"]}] + (results or [])

            # Fallback: กรองแล้วไม่เจอ
            if not results and force_category:
                print(f"[RAG] No results with filter → retrying full search")
                results = self.kb_loader.search(
                    query=enriched_query, save_name=self.index_name,
                    top_k=top_k, force_category=None
                )

            if not results: return []

            formatted = []
            for res in results:
                if isinstance(res, dict):
                    formatted.append({
                        "text":  res.get("chunk", res.get("text","")),
                        "score": res.get("distance", res.get("score", 0.0))
                    })
                elif isinstance(res, str):
                    formatted.append({"text":res,"score":0.0})

            if label == "curriculum_info" and formatted:
                formatted = self._rerank_curriculum(formatted, entities)
                formatted = formatted[:5]
                # Marker สำหรับ LLM
                if formatted and formatted[0].get("score",0) >= 14:
                    formatted[0]["text"] = (
                        "=== [ข้อมูลที่ตรงกับคำถามมากที่สุด — อ่านข้อนี้ก่อน] ===\n"
                        + formatted[0]["text"]
                        + "\n=== [สิ้นสุดข้อมูลหลัก] ==="
                    )

            # Cross-search: coop + บริษัท → MOU
            _company_kw = ["บริษัท","erp","robot","ai","software","tech","automation","cloud","data","ซอฟต์แวร์"]
            if label == "coop_intern" and any(w in query.lower() for w in _company_kw):
                mou = self.kb_loader.search(query=enriched_query, save_name=self.index_name,
                                             top_k=5, force_category="[หมวดหมู่: เครือข่ายบริษัท/MOU]")
                if mou:
                    print(f"[RAG] cross-search MOU → {len(mou)} chunks")
                    for m in mou: formatted.append({"text":m.get("chunk",m.get("text","")),"score":5.0})

            # Cross-search: mou + อาจารย์ → staff
            _teacher_kw = ["อาจารย์","สอน","ผู้สอน","lecturer","instructor"]
            if label == "mou_company" and any(w in query.lower() for w in _teacher_kw):
                staff = self.kb_loader.search(query=enriched_query, save_name=self.index_name,
                                               top_k=5, force_category="[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]")
                if staff:
                    print(f"[RAG] cross-search staff_info → {len(staff)} chunks")
                    for s in staff: formatted.append({"text":s.get("chunk",s.get("text","")),"score":5.0})

            return formatted

        except Exception as e:
            print(f"[RAG Error] Retrieval failed: {e}")
            return []