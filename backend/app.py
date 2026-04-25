import os
import time
import logging
import json
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pythainlp.tokenize import word_tokenize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

from ai_core.rag_handler import RAGHandler
from ai_core.llm_interface import LLMInterface
from ai_core.response_formatter import ResponseFormatter
from voice.tts_engine import TTSEngine
from ai_core.intent_classifier import ThaiIntentClassifier

app = FastAPI()

rag = RAGHandler()
llm = LLMInterface()
tts = TTSEngine()

intent_classifier = ThaiIntentClassifier()
try:
    intent_classifier.load()
except FileNotFoundError as e:
    logging.warning(f"[Intent] ข้าม Intent Classifier: {e}")
    intent_classifier = None

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str

request_counter = 1

# =========================================================
# Memory (ความจำระหว่าง session)
# =========================================================
bot_memory = {
    "intent":          "",
    "intent_group":    "",
    "year":            "",
    "generation":      "",
    "semester":        "",
    "curriculum_year": "",
    "sid_prefix":      "",
}

# [อัปเดต] Mapping รหัสนักศึกษา 2 หน้า → รุ่นย่อยและปีหลักสูตร
COHORT_CONFIG = {
    "63": {"curr": "2563", "gens": ["1/1", "1/2", "2"]},
    "64": {"curr": "2563", "gens": ["1/1", "1/2", "2"]},
    "65": {"curr": "2565", "gens": ["1/1", "1/2", "2"]},
    "66": {"curr": "2565", "gens": ["1/1", "1/2", "2"]},
    "67": {"curr": "2565", "gens": ["1/1", "1/2", "2"]},
    "68": {"curr": "2568", "gens": ["1/1", "1/2", "2"]},
}

# กลุ่ม intent ที่ควรจำข้ามรอบ
INTENT_GROUP_MAP = {
    "curriculum_info": "CURRICULUM",
    "course_desc":     "CURRICULUM",
    "career_info":     "CAREER",
    "major_info":      "MAJOR",
    "staff_info":      "STAFF",
    "admission_info":  "ADMISSION",
    "coop_intern":     "COOP",
    "mou_company":     "MOU",
    "general_info":    "GENERAL",
}

# Intent ที่ "reset" ความจำเรื่อง curriculum (เปลี่ยนเรื่องแล้ว)
MEMORY_RESET_INTENTS = {"greeting", "small_talk", "toxic", "out_of_scope", "report_issue"}
# =========================================================


@app.get("/")
def read_root():
    return {"message": "AIDA API is running successfully!"}


@app.post("/ask")
async def ask_aida(request: ChatRequest):
    global request_counter, bot_memory
    user_message = request.query

    current_id = f"G{request_counter:02d}"
    request_counter += 1

    logging.info(f"--- [NEW REQUEST ID: {current_id}] เริ่มประมวลผลคำถาม: '{user_message}' ---")
    start_total_time = time.perf_counter()
    start_logic      = time.perf_counter()

    # ---------------------------------------------------------
    # [สเต็ป 0] Intent Classification
    # ---------------------------------------------------------
    start_intent_time = time.perf_counter()
    if intent_classifier is not None:
        intent_data      = intent_classifier.predict(user_message)
        detected_intent  = intent_data["intent"]["label"]
        display_intent   = intent_data["intent"]["display_name"]
        entities         = intent_data["entities"]
    else:
        intent_data     = {"intent": {"label": "unknown", "display_name": "ไม่ระบุ"}, "entities": {}}
        detected_intent = "unknown"
        display_intent  = "ไม่ระบุ"
        entities        = {}

    intent_latency = time.perf_counter() - start_intent_time

    # =========================================================
    # [สเต็ป 0.5] Memory & Silent Mapping (เพิ่ม Advance Logic)
    # =========================================================

    # 1. Regex เพิ่มเติม: ชั้นปี (1-6) และเทอม (1-3)
    m_year = re.search(r"ปี\s*([1-6])(?!\d)", user_message)
    if m_year:
        entities["year"] = m_year.group(1)

    m_sem = re.search(r"เทอม\s*([1-3])\b", user_message)
    if m_sem:
        entities["semester"] = m_sem.group(1)

    # 2. Silent Mapping: cohort prefix 63-69 → หลักสูตร & เตรียมถามรุ่นย่อย
    match_id = re.search(r"\b(6[3-9])\b", user_message)
    if match_id:
        sid = match_id.group(1)
        if sid in COHORT_CONFIG:
            entities["curriculum_year"] = COHORT_CONFIG[sid]["curr"]
            bot_memory["sid_prefix"] = sid # จำรหัส 2 ตัวหน้าไว้ใช้ถามกลับ
            # ถ้าปีนั้นมีรุ่นเดียว จับยัดให้เลยไม่ต้องถาม
            if len(COHORT_CONFIG[sid]["gens"]) == 1:
                entities["generation"] = COHORT_CONFIG[sid]["gens"][0]

    # [เพิ่ม] ดักจับรุ่นย่อยจากข้อความ (เช่น 1/1, 1/2, /1, /2 หรือ รุ่น 2)
    m_gen = re.search(r"(1/1|1/2|\b2\b|/1|/2)", user_message)
    if m_gen:
        gen_val = m_gen.group(1).replace("/", "1/") if "/" in m_gen.group(1) and len(m_gen.group(1)) == 2 else m_gen.group(1)
        entities["generation"] = gen_val

    # [เพิ่มใหม่] ดึงสติบอท: ถ้าเจอข้อมูลตัวเลข ห้ามมองว่าเป็น small_talk เด็ดขาด! (แก้บั๊กตอบ "ปี 65 ครับ" แล้วลืม)
    has_important_data = bool(m_year or m_sem or match_id or m_gen)
    if has_important_data and bot_memory["intent"] in ["curriculum_info", "course_desc"]:
        detected_intent = bot_memory["intent"]
        intent_data["intent"]["label"] = detected_intent
        logging.info(f"[Intent Override] เจอข้อมูลตอบกลับ ดึงสติเข้าเรื่อง {detected_intent} ป้องกันการล้างความจำ!")

    # 3. Memory Recovery: ถ้า intent ใหม่เป็น unknown/greeting แต่เคยคุยเรื่องหนึ่งอยู่
    new_group = INTENT_GROUP_MAP.get(detected_intent, "")

    if detected_intent in MEMORY_RESET_INTENTS:
        # เปลี่ยนเรื่องชัดเจน — ล้าง memory บางส่วน
        if bot_memory["intent_group"] and bot_memory["intent_group"] != new_group:
            logging.info(f"[Memory] เปลี่ยนเรื่องจาก {bot_memory['intent_group']} ไป {new_group or 'NONE'} -> ล้างความจำระยะสั้น")
            bot_memory.update({"year": "", "generation": "", "semester": "", "curriculum_year": "", "sid_prefix": ""})
    elif detected_intent in ("unknown", "out_of_scope") and bot_memory["intent"]:
        # ไม่ชัดเจน → ใช้ intent เดิม
        detected_intent = bot_memory["intent"]
        intent_data["intent"]["label"] = detected_intent

    # 4. อัปเดต memory ด้วย intent ที่มีความหมาย
    if detected_intent not in {*MEMORY_RESET_INTENTS, "unknown", "out_of_scope"}:
        bot_memory["intent"]       = detected_intent
        bot_memory["intent_group"] = INTENT_GROUP_MAP.get(detected_intent, "")

    # 5. อัปเดต memory entity
    for key in ("year", "generation", "semester", "curriculum_year"):
        if entities.get(key):
            bot_memory[key] = entities[key]

    # 6. เติม entity จาก memory (ถ้าหายไป)
    for key in ("year", "generation", "semester", "curriculum_year"):
        if not entities.get(key) and bot_memory[key]:
            entities[key] = bot_memory[key]

    logging.info(
        f"[Memory] สถานะ: ปี {entities.get('year')}, เทอม {entities.get('semester')}, "
        f"รหัสอ้างอิง(รุ่น {entities.get('generation')}, หลักสูตร {entities.get('curriculum_year')})"
    )

    # 7. API Saver (Validator) — เฉพาะ curriculum_info
    if detected_intent == "curriculum_info":
        is_missing   = False
        val_display  = ""
        val_speech   = ""

        sid = bot_memory.get("sid_prefix")

        if not entities.get("year"):
            is_missing  = True
            val_display = "น้องไอด้าขอทราบชั้นปีหน่อยค่ะ (เช่น ปี 1, ปี 2) จะได้เปิดดูแผนการเรียนให้ถูกต้องนะคะ"
            val_speech  = "น้องไอด้าขอทราบชั้นปีหน่อยค่ะ จะได้เปิดดูแผนการเรียนให้ถูกต้องนะคะ"
        elif not sid and not entities.get("generation"):
            is_missing  = True
            val_display = "น้องไอด้าขอทราบรหัสนักศึกษา 2 ตัวหน้าหน่อยค่ะ (เช่น 65, 66) จะได้ดึงแผนการเรียนเป๊ะๆ ให้นะคะ"
            val_speech  = "น้องไอด้าขอทราบรหัสนักศึกษา 2 ตัวหน้าหน่อยค่ะ จะได้ดึงแผนการเรียนเป๊ะๆ ให้นะคะ"
        elif sid and sid in COHORT_CONFIG:
            available_gens = COHORT_CONFIG[sid]["gens"]
            if len(available_gens) > 1 and not entities.get("generation"):
                is_missing = True
                gen_list_text = " หรือ ".join(available_gens)
                val_display = f"รุ่นที่เท่าไหร่คะ (รุ่น {gen_list_text}) 😊"
                val_speech = "รุ่นที่เท่าไหร่คะ 😊"

        if is_missing:
            logging.info("[API Saver] ข้อมูลไม่ครบ → ตัดจบก่อนเข้า LLM!")
            audio_path = await tts.generate_voice(val_speech)
            return {
                "answer":   val_display,
                "audio_url": audio_path,
                "emotion":  "Curious",
                "intent":   detected_intent,
                "performance_report": {"note": "Short-circuited: missing year/generation/clarification"},
            }

    # =========================================================

    # ---------------------------------------------------------
    # สเต็ป 1: RAG Retrieval
    # ---------------------------------------------------------
    start_rag_time = time.perf_counter()
    search_results = rag.retrieve(query=user_message, intent_result=intent_data, top_k=6)
    rag_latency    = time.perf_counter() - start_rag_time

    # ---------------------------------------------------------
    # สเต็ป 2 & 3: LLM Inference & Formatting
    # ---------------------------------------------------------
    start_llm_time = time.perf_counter()
    raw_ai_response = llm.generate_response(
        query=user_message,
        retrieval_results=search_results,
        intent_result=intent_data,
    )
    final_response = ResponseFormatter.format_output(raw_ai_response, intent_result=intent_data)
    llm_latency    = time.perf_counter() - start_llm_time

    logic_delay  = time.perf_counter() - start_logic
    display_text = final_response["display_text"]
    speech_text  = final_response["speech_text"]
    emotion      = final_response["emotion"]

    words      = [w for w in word_tokenize(speech_text, engine="newmm") if w.strip()]
    word_count = len(words)
    length_newmm = "Short" if word_count <= 20 else ("Medium" if word_count <= 50 else "Long")

    # ---------------------------------------------------------
    # สเต็ป 4: TTS Generation
    # ---------------------------------------------------------
    start_tts_time = time.perf_counter()
    audio_path     = await tts.generate_voice(speech_text)
    tts_latency    = time.perf_counter() - start_tts_time

    audio_url        = audio_path if audio_path else None
    e2e_total_latency = time.perf_counter() - start_total_time

    duration   = max(word_count * 0.35, 0.1)
    total_time = logic_delay + tts_latency

    performance_report = {
        "User_Dialogue":      user_message,
        "ID":                 current_id,
        "Intent_Detected":    display_intent,
        "Extracted_Entities": entities,
        "word_count":         word_count,
        "length_newmm":       length_newmm,
        "Intent_Latency":     round(intent_latency, 4),
        "RAG_Latency":        round(rag_latency, 4),
        "LLM_Latency":        round(llm_latency, 4),
        "Logic_Delay":        round(logic_delay, 4),
        "TTS_Latency":        round(tts_latency, 4),
        "Duration":           round(duration, 2),
        "RTF":                round(total_time / duration, 4),
        "Total_Time":         round(total_time, 4),
        "E2E_Total_Latency":  round(e2e_total_latency, 4),
        "TTS_Script":         speech_text,
    }

    print(
        "\n" + "=" * 60 + "\n📊 PERFORMANCE REPORT\n"
        + json.dumps(performance_report, ensure_ascii=False, indent=4)
        + "\n" + "=" * 60
    )

    return {
        "answer":             display_text,
        "audio_url":          audio_url,
        "emotion":            emotion,
        "intent":             detected_intent,
        "performance_report": performance_report,
    }