# Voice
ระบบ **Text-to-Speech** ทำให้เกิดผู้ช่วยเสมือนที่พูดได้
ภายในโฟลเดอร์นี้จะทำหน้าที่ดูแลเรื่อง Text to Speech โดยเฉพาะ หน้าที่: Bam 
โดยจะทำหน้าที่เป็น engine เสียง Internal Service เพื่อรอรับ input text จาก rag ใน ai_core(พี่โป่ง) และประมวลผลเสียงออกมาเก็บ mp3 อยู่ใน static folder เป็น output เพื่อให้โต้นำไปทำสร้าง endpoint เสียงคำตอบของไอด้าและนำไปเชื่อมกับ fontend จริงๆ
---

## 📂 โครงสร้างโปรเจ็ค
```bash
AIDA/
├── backend/ # AI Core + Voice modules
│   ├── Voice
│       ├── stt_ttsweek2 # สำหรับทดสอบประสิทธิภาพ runtime + adjust เสียง เป็นการทดสอบก่อนนำมาใช้จริง
│       ├── tts_engine.py # เป็น engine จริงที่ใช้เชื่อมต่อกับ rag ประมวลผลข้อมูลออกมาเป็น file เสียง
│   ├── static/           <-- โฟลเดอร์เก็บไฟล์เสียงของไอด้า ใช้ในการตอบ
│   └── audio_responses/ <-- ไฟล์ .mp3 จะอยู่ในนี้

```

**ไฟล์หลัก:**
- `tts_engine.py`  ใช้ในการเชื่อมกับ rag 
---

📌 หมายเหตุ
การเชื่อมต่อกับ fontend: ไฟล์เสียงอยู่ที่ path /static/audio_responses นะ อย่าลืม Mount path นี้ด้วย

วิธีลง pip list --format=freeze > requirements.txt

Flow
Frontend (เจแปน): ส่งคำถามว่า "ไอด้า ปี 1 เรียนอะไร?" ไปที่ /chat
↓
API Endpoint (โต้): รับคำถามมา แล้วไปสะกิด RAG (พี่โป่ง)
↓
RAG (พี่โป่ง): หาคำตอบมาให้ในรูปแบบ JSON 
↓
TTS Engine (แบม): รับ JSON นั้นมาเปลี่ยนเป็นไฟล์เสียง aida_123.mp3
↓
API Response (โต้): รวมร่างทุกอย่างส่งกลับไปให้เจแปน:

📚 แหล่งอ้างอิง
gTTS
EdgeTTS
TELECOMMUNICATION STANDARDIZATION SECTOR OF ITU