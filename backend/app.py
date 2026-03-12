import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # 1. เพิ่มตัวจัดการไฟล์ static
from pydantic import BaseModel

# 2. นำเข้าคลาส Engine เสียงของแบม (สมมติว่าไฟล์ app.py อยู่ในโฟลเดอร์ backend)
from voice.tts_engine import TTSEngine
from ai_core.rag_handler import RAGHandler

# 3. สร้างระบบเสียงของแบมเตรียมไว้เลย (***บรรทัดนี้แหละที่จะสร้างโฟลเดอร์ static ให้คุณ!***)
tts = TTSEngine()

app = FastAPI()

rag = RAGHandler()

# 4. เปิดให้ Frontend เข้าถึงโฟลเดอร์ static เพื่อโหลดไฟล์ mp3 ได้
# (อิงจากโค้ดแบม โฟลเดอร์จะชื่อ static เราจึงตั้งค่าให้อ่านจากโฟลเดอร์นี้)
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

@app.get("/")
def read_root():
    return {"message": "AIDA API is running successfully!"}

@app.post("/ask")
async def ask_aida(request: ChatRequest):
    user_message = request.query
    
    # สเต็ป 1: ค้นหาข้อมูลจาก RAG
    search_results = rag.retrieve(query=user_message, top_k=1) 
    
    if search_results and len(search_results) > 0:
        # ได้ข้อความดิบมา (มี [SOURCE: ...] ติดมาด้วย)
        raw_text = search_results[0]["text"]
        
        # --- พระเอกของเราอยู่ตรงนี้: ทำความสะอาดข้อความ ---
        # 1. ลบทุกอย่างที่อยู่ในวงเล็บเหลี่ยม [...] ทิ้งไป
        clean_text = re.sub(r'\[.*?\]', '', raw_text)
        # 2. ลบเครื่องหมาย ### ทิ้งไป
        clean_text = clean_text.replace('###', '')
        # 3. ตัดช่องว่างที่อาจจะเหลือทิ้งไว้หัวท้าย
        ai_response_text = clean_text.strip()
        
    else:
        ai_response_text = "ขออภัยค่ะ ไอด้าหาข้อมูลเรื่องนี้ไม่พบค่ะ"
    
    # ---------------------------------------------------------
    # ส่วนที่ 2: Engine เสียงของแบม
    # ---------------------------------------------------------
    audio_path = await tts.generate_voice(ai_response_text)
    
    if audio_path:
        audio_url = f"http://127.0.0.1:8000{audio_path}"
    else:
        audio_url = None

    # ---------------------------------------------------------
    # ส่วนที่ 3: ส่งของกลับให้เจแปน (Frontend)
    # ---------------------------------------------------------
    return {
        "answer": ai_response_text,
        "audio_url": audio_url
    }