# voice (TTS) and test STT
**Voice Model**  ใช้ Library แบบ "Bridge" ที่ประมวลผลบน server มี 2 ตัว: edgetts, gtts
**1. Edge_TTS** เป็นการดึงเสียงมาจาก Read Aloud Feature ของ MicrosoftEdge Browser ผ่าน Websocket (คุยแบบreal-time) เพื่อขอเสียงมาเล่นให้ userฟัง
**2. gTTS** เป็นการดึงเสียงมาจากฟีเจอร์ google translate เหมือนกัน
ซึ่ง 2 ตัวนี้นั้น require Internet และอาจมีปัจจัยเรื่อง Network Overhead เข้ามาเกี่ยวข้องในเรื่องของ Latency ในโฟลเดอร์นี้เป็นส่วนของการวิจัย bencmark เทียบระหว่างสองโมเดลเสียงในช่วง week2,3 

---

## 📂 โครงสร้างโปรเจ็ค
```bash
AIDA/
├── README.md
├── backend/ # AI Core + Voice modules
    └──  Voice/
    └──  stt_ttsweek2/ # Main folder 
        └──  engine # ฟังก์ชั่นการรับ text จาก serverและหาkeyword คำตอบแล้วแปลงเป็นเสียงส่งให้server
        └──  logs # ประวัติบันทึก Bencmark ของ gtts/edgetts
    └──  server # หน้าบ้าน
---
```

**ไฟล์หลัก:**
- `backend/Voice/engine/edgetts_engine.py,gtts_engine.py`  
- `backend/Voice/server_edgetts.py,server_gtts.py`  
- `backend/Voice/speech.js`  

---

## ⚙️ วิธีใช้งานเบื้องต้น
1. **Clone repository**
```bash
git clone https://github.com/yourusername/AIDA.git
cd AIDA
ติดตั้ง dependencies

pip install -r requirements.txt
cd backend / voice/ stt_ttsweek2

python server_edgetts.py
python server_gtts.py

📌 หมายเหตุ
เข้ามายังBranch dialogue/bam-d1t
ควรอ่าน README 
โฟลเดอร์ Helping เป็นการช่วยเหลือและคำอธิบายวิธีการทำงานใน Environment นี้วิธีการ Import function ข้ามโฟลเดอร์

📚 แหล่งอ้างอิง
edgeTTS
gTTS
Response Times UX/UI by Nielsen