from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# ตั้งค่า CORS ให้ Frontend (Next.js) เข้าถึง API นี้ได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # อนุญาตทุกโดเมน (สำหรับช่วงพัฒนา)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# กำหนดรูปแบบข้อมูลที่รอรับจาก Frontend (ต้องมี key ชื่อ query)
class ChatRequest(BaseModel):
    query: str

# สร้าง Endpoint /ask แบบ POST
@app.post("/ask")
async def ask_aida(request: ChatRequest):
    user_message = request.query
    print(f"ได้รับคำถามจาก Frontend: {user_message}")
    
    # เอาโค้ด RAG / โมเดล AI ของคุณมาเสียบตรงนี้ได้เลย

    # จำลองคำตอบที่จะส่งกลับไป
    ai_response_text = f"ไอด้าได้รับข้อความของคุณแล้วค่ะ (คุณพิมพ์มาว่า: {user_message})"
    
    return {
        "answer": ai_response_text
    }