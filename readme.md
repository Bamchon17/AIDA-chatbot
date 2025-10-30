# AIDA: ผู้ช่วยเสมือน AI สำหรับคณะวิศวกรรมศาสตร์ AI และ Data Science
**AIDA** เป็น Virtual Mascot Chatbot ที่ออกแบบมาเพื่อโต้ตอบกับนักศึกษาและให้ข้อมูลเกี่ยวกับคณะวิศวกรรมศาสตร์ AI และ Data Science ของ Bangkok University จัดทำโดยกลุ่มนักศึกษาโปรเจ็คจบเท่านั้น
**AIDA** is a Virtual Mascot Chatbot designed to interact with students and provide information about the Faculty of Engineering AI and Data Science.  
It combines **AI-driven conversation**, **Text-to-Speech**, and an **interactive avatar**, creating a friendly and intelligent virtual assistant for graduated project only 

ระบบรวม **AI สนทนาอัจฉริยะ**, **Text-to-Speech**, และ **Avatar โต้ตอบได้** ทำให้เกิดผู้ช่วยเสมือนที่เป็นมิตรและฉลาด

---

## 📂 โครงสร้างโปรเจ็ค

AIDA/
├── README.md
├── backend/ # AI Core + Voice modules
├── frontend/ # UI + Avatar
├── scripts/ # เครื่องมือช่วย preprocess ข้อมูล
├── database/ # ฐานความรู้ + Embeddings
├── notebooks/ # Jupyter notebook สำหรับทดลอง
├── docs/ # เอกสารและ diagram
└── demos/ # วิดีโอตัวอย่างการใช้งาน

markdown
Copy code

---

## 👥 หน้าที่ของทีม

### 1️⃣ AI Core Developer – พี่โป่ง
**โฟลเดอร์:** `backend/ai_core`  
**หน้าที่:**
- เชื่อมต่อ LLM (GPT / Gemini / Ollama)  
- ทำ RAG logic (LangChain + FAISS/ChromaDB)  
- แปลงผลลัพธ์ให้พร้อมสำหรับ Text-to-Speech  
- ทำงานร่วมกับ Knowledge Engineer เพื่อดึงข้อมูลจากฐานความรู้  

**ไฟล์หลัก:**
- `llm_interface.py`  
- `rag_handler.py`  
- `response_formatter.py`  

---

### 2️⃣ Speech & Voice Engineer – แบม
**โฟลเดอร์:** `backend/voice`  
**หน้าที่:**
- ทำ Text-to-Speech (gTTS / Edge TTS / OpenAI TTS)  
- ทำ Speech-to-Text (Whisper / Google STT)  
- ทำ lip-sync ให้ Avatar เคลื่อนไหวตามเสียง  
- ปรับเสียงให้ฟังน่ารักและใส่อารมณ์ (option)  

**ไฟล์หลัก:**
- `tts.py`  
- `stt.py`  
- `lip_sync.py`  

---

### 3️⃣ UI/UX & Avatar Designer – จป.
**โฟลเดอร์:** `frontend/`  
**หน้าที่:**
- ออกแบบ UI และหน้าเว็บสำหรับ chatbot  
- แสดง Avatar และ emotion ของตัวละคร  
- ทำให้ระบบใช้งานง่ายและดูเหมือน VTuber จริง  

**ไฟล์หลัก:**
- `app.py`  
- `components/`  
- `assets/avatars/`  
- `assets/css/`  

---

### 4️⃣ Knowledge Engineer – แก๊ง
**โฟลเดอร์:** `backend/database/` + `scripts/`  
**หน้าที่:**
- รวบรวมข้อมูลสาขา (รายวิชา, อาจารย์, FAQ)  
- preprocess ข้อมูลและ generate embeddings สำหรับ RAG  
- ตรวจสอบให้ฐานข้อมูลแม่นยำและอัพเดตง่าย  

**ไฟล์หลัก:**
- `kb_loader.py`  
- `scripts/preprocess_knowledge.py`  
- `scripts/generate_embeddings.py`  

---

### 5️⃣ System Integrator & Tester – โต้
**โฟลเดอร์:** `backend/tests/`, `frontend/`, `demos/`  
**หน้าที่:**
- รวมทุก module ให้ทำงานร่วมกัน (AI Core + Voice + Frontend)  
- ทดสอบระบบ end-to-end  
- แก้ bug, ปรับ performance  
- ทำ demo video และ presentation  

**ไฟล์หลัก:**
- `backend/tests/test_ai_core.py`  
- `backend/tests/test_voice.py`  
- `demos/sample_interactions.mp4`  

---

## ⚙️ วิธีใช้งานเบื้องต้น

1. **Clone repository**
```bash
git clone https://github.com/yourusername/AIDA.git
cd AIDA
ติดตั้ง dependencies

pip install -r requirements.txt
รัน backend

cd backend
python app.py
รัน frontend

cd frontend
streamlit run app.py

📌 หมายเหตุ
สมาชิกแต่ละคนทำงานในโฟลเดอร์ของตัวเอง
ใช้ branch แยกตามหน้าที่ เช่น feature/ai_core, feature/voice, etc.
ควรอัปเดต README เมื่อมีการเปลี่ยนแปลงสำคัญ
โฟลเดอร์ Helping เป็นการช่วยเหลือและคำอธิบายวิธีการทำงานใน Environment นี้วิธีการ Import function ข้ามโฟลเดอร์

📚 แหล่งอ้างอิง
LangChain Documentation
Live2D
gTTS
OpenAI GPT API