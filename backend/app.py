import os
import time
import logging
import json # เพิ่มเพื่อจัดการการแสดงผล
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- นำเข้าไลบรารีตัดคำภาษาไทย (PyThaiNLP) ---
from pythainlp.tokenize import word_tokenize

# --- ตั้งค่า Logging สำหรับเก็บข้อมูล Performance ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# --- 1. นำเข้าไฟล์ของเพื่อนให้ครบทั้ง 3 ส่วน ---
from ai_core.rag_handler import RAGHandler
from ai_core.llm_interface import LLMInterface
from ai_core.response_formatter import ResponseFormatter
from voice.tts_engine import TTSEngine

# [เพิ่มใหม่] นำเข้า Intent Classifier
from ai_core.intent_classifier import ThaiIntentClassifier

app = FastAPI()

# --- 2. เรียกใช้งานระบบทั้งหมด ---
rag = RAGHandler()
llm = LLMInterface()
tts = TTSEngine()

# [เพิ่มใหม่] โหลดโมเดล Intent ไว้ในหน่วยความจำตอนเปิดเซิร์ฟเวอร์
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

request_counter = 1  # ตัวนับ ID

@app.get("/")
def read_root():
    return {"message": "AIDA API is running successfully!"}

@app.post("/ask")
async def ask_aida(request: ChatRequest):
    global request_counter
    user_message = request.query
    
    current_id = f"G{request_counter:02d}"
    request_counter += 1

    logging.info(f"--- [NEW REQUEST ID: {current_id}] เริ่มประมวลผลคำถาม: '{user_message}' ---")
    
    # จับเวลาภาพรวมทั้งหมด (End-to-End)
    start_total_time = time.perf_counter()
    start_logic = time.perf_counter() # เริ่มจับเวลาส่วน Logic รวม
    
    # ---------------------------------------------------------
    # [เพิ่มใหม่] สเต็ป 0: Intent Classification (แยกหมวดหมู่คำถาม)
    # ---------------------------------------------------------
    start_intent_time = time.perf_counter()
    if intent_classifier is not None:
        intent_data = intent_classifier.predict(user_message)
        detected_intent = intent_data["intent"]["label"]
        display_intent = intent_data["intent"]["display_name"]
        entities = intent_data["entities"]
    else:
        detected_intent = "unknown"
        display_intent = "ไม่ระบุ"
        entities = {}
    intent_latency = time.perf_counter() - start_intent_time

    logging.info(f"[Intent] หมวดหมู่: {display_intent} | ใช้เวลา: {intent_latency:.4f} วินาที")
    
    # ---------------------------------------------------------
    # สเต็ป 1: RAG Retrieval (วัดเวลาการค้นหาข้อมูล)
    # ---------------------------------------------------------
    start_rag_time = time.perf_counter()
    
    # 💡 [แนะนำเพิ่มเติม]: คุณสามารถประยุกต์ใช้ Intent/Entities ตรงนี้ได้ 
    # เช่น ถ้ารู้ว่าเป็นรายวิชา สามารถเอา entities["course_code"] ไปต่อท้าย query 
    # เพื่อให้ RAG ค้นหาได้แม่นยำขึ้น เช่น: query=f"{user_message} {entities['course_code']}"
    
    search_results = rag.retrieve(query=user_message, top_k=6)
    rag_latency = time.perf_counter() - start_rag_time
    logging.info(f"[RAG] ใช้เวลาค้นหาข้อมูล: {rag_latency:.4f} วินาที")
    
    # ---------------------------------------------------------
    # สเต็ป 2 & 3: LLM Inference & Formatting (วัดเวลาคิดคำตอบและจัดฟอร์แมต)
    # ---------------------------------------------------------
    start_llm_time = time.perf_counter()
    
    # 💡 [แนะนำเพิ่มเติม]: คุณอาจจะส่ง detected_intent เข้าไปใน llm.generate_response ด้วย
    # เพื่อให้ LLM รู้ว่าควรตอบบริบทไหน (ถ้าฟังก์ชันเพื่อนรองรับ)
    raw_ai_response = llm.generate_response(query=user_message, retrieval_results=search_results)
    final_response = ResponseFormatter.format_output(raw_ai_response)
    
    llm_latency = time.perf_counter() - start_llm_time
    logging.info(f"[LLM] ใช้เวลาคิดคำตอบและจัดรูปแบบ: {llm_latency:.4f} วินาที")
    
    # คำนวณเวลา Logic_Delay (Intent + RAG + LLM)
    logic_delay = time.perf_counter() - start_logic
    
    display_text = final_response["display_text"]
    speech_text = final_response["speech_text"]
    emotion = final_response["emotion"]
    
    # ---------------------------------------------------------
    # วิเคราะห์ข้อความด้วย PyThaiNLP เพื่อหาจำนวนคำและจัดระดับ
    # ---------------------------------------------------------
    words = [w for w in word_tokenize(speech_text, engine="newmm") if w.strip()]
    word_count = len(words)
    
    if word_count <= 20:
        length_newmm = "Short"
    elif word_count <= 50:
        length_newmm = "Medium"
    else:
        length_newmm = "Long"

    # ---------------------------------------------------------
    # สเต็ป 4: TTS Generation (วัดเวลาสร้างไฟล์เสียง)
    # ---------------------------------------------------------
    start_tts_time = time.perf_counter()
    audio_path = await tts.generate_voice(speech_text)
    tts_latency = time.perf_counter() - start_tts_time
    logging.info(f"[TTS] ใช้เวลาสังเคราะห์เสียง: {tts_latency:.4f} วินาที")
    
    if audio_path:
        audio_url = f"http://127.0.0.1:8000{audio_path}"
    else:
        audio_url = None

    # สรุปเวลาทั้งหมด
    e2e_total_latency = time.perf_counter() - start_total_time
    logging.info(f"--- [DONE] ใช้เวลาประมวลผลรวมทั้งหมด (End-to-End Latency): {e2e_total_latency:.4f} วินาที ---\n")

    # ---------------------------------------------------------
    # คำนวณสูตรวัดผล (Duration, RTF, WPM, SPW)
    # ---------------------------------------------------------
    duration = word_count * 0.35  # ความเร็วพูดจำลอง (วินาทีต่อคำ)
    if duration <= 0: duration = 0.1 
    
    total_time = logic_delay + tts_latency
    rtf = total_time / duration
    wpm = (word_count / duration) * 60
    spw = duration / word_count

    # [เพิ่มใหม่] อัปเดต Dictionary สำหรับเก็บ Report ให้มีข้อมูล Intent
    performance_report = {
        "User_Dialogue": user_message,
        "ID": current_id,
        "Intent_Detected": display_intent,         # <--- เพิ่มข้อมูล Intent ลงใน Report
        "Extracted_Entities": entities,            # <--- เพิ่มข้อมูล Entity ลงใน Report
        "word_count": word_count,
        "length_newmm": length_newmm,
        "Intent_Latency": round(intent_latency, 4),# <--- เพิ่มเวลาประมวลผล Intent
        "Logic_Delay": round(logic_delay, 4),
        "TTS_Latency": round(tts_latency, 4),
        "Duration": round(duration, 2),
        "RTF": round(rtf, 4),
        "Total_Time": round(total_time, 4),
        "E2E_Total_Latency": round(e2e_total_latency, 4),
        "WPM": round(wpm, 2),
        "SPW": round(spw, 4),
        "TTS_Script": speech_text
    }

    # พิมพ์ Report ออกมาที่ Terminal ให้มองเห็นได้ทันที
    print("\n" + "="*60)
    print("📊 PERFORMANCE REPORT (อัปเดตระบบ Intent แล้ว)")
    print("="*60)
    print(json.dumps(performance_report, ensure_ascii=False, indent=4))
    print("="*60 + "\n")

    # ---------------------------------------------------------
    # สเต็ป 5: ส่งของกลับให้ Frontend (แนบ Report และ Intent ไปด้วย)
    # ---------------------------------------------------------
    return {
        "answer": display_text,
        "audio_url": audio_url,
        "emotion": emotion,
        "intent": detected_intent,        # <--- โยน Intent กลับไปเผื่อ Frontend อยากใช้
        "performance_report": performance_report
    }