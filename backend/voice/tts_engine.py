# backend/voice/tts_engine.py
import asyncio
import edge_tts
import os
import uuid
import time 
from pathlib import Path 

class TTSEngine:
    def __init__(self):
        # ค่า Parameter ที่จูนมา (ดีที่สุดสำหรับหูคนฟังตอนนี้)
        self.voice = "th-TH-PremwadeeNeural"
        self.rate = "-3%"
        self.pitch = "+13Hz"
        
        # --- ปรับ Path ให้เป็นระบบ Global (ทำงานได้ทุก OS) ---
        self.base_dir = Path(__file__).resolve().parent.parent
        self.output_dir = self.base_dir / "static" / "audio_responses"

        # สร้างโฟลเดอร์แบบปลอดภัย
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"[TTS Info] Audio directory ready at: {self.output_dir}")

    def cleanup_old_files(self, max_age_seconds=600):
        """
        แอบไปลบไฟล์เก่าๆ แบบไม่รบกวนความเร็วระบบหลัก
        """
        try:
            now = time.time()
            # ใช้ .glob เพื่อค้นหาเฉพาะไฟล์ mp3 อย่างรวดเร็ว
            for file_path in self.output_dir.glob("*.mp3"):
                if file_path.stat().st_mtime < now - max_age_seconds:
                    file_path.unlink() # ลบไฟล์
        except Exception as e:
            print(f"[Cleanup Error] {e}")

    async def generate_voice(self, text, emotion="Normal"):
        """
        รับคำตอบจากพี่โป่ง แล้วส่งเสียงให้เจแปน
        """
        if not text:
            return None

        # 1. ทำความสะอาดก่อน (แนะนำให้ใส่ใน try-except ของตัวเองเพื่อไม่ให้ขัดจังหวะการเจนเสียง)
        self.cleanup_old_files()

        # 2. สร้างชื่อไฟล์และ Path
        filename = f"aida_{uuid.uuid4().hex[:8]}.mp3"
        full_path = self.output_dir / filename

        try:
            # 3. เจนเสียงด้วย Edge-TTS
            communicate = edge_tts.Communicate(
                text=text, 
                voice=self.voice, 
                rate=self.rate, 
                pitch=self.pitch
            )
            await communicate.save(str(full_path))
            
            # 4. ส่ง Path แบบที่ API เข้าใจ (Relative Path)
            return f"/static/audio_responses/{filename}"
            
        except Exception as e:
            print(f"[TTS Error] Pipeline failed: {e}")
            return None
        
# # --- ส่วนทดสอบรันเฉพาะไฟล์ ---
# if __name__ == "__main__":
#     async def test():
#         engine = TTSEngine()
#         print("กำลังทดสอบเจนเสียงพร้อมระบบ Auto-Cleanup...")
        
#         test_text = "สาขาของเราเป็นหลักสูตรแรกและหลักสูตรเดียวในไทยค่ะ เรามุ่งเน้นการเรียนรู้เพื่อพัฒนาอุตสาหกรรมข้อมูลและปัญญาประดิษฐ์ เชื่อมโยงกับองค์ความรู้รอบตัวทั้ง ทักษะปัญญาประดิษฐ์ วิทยาการข้อมู"
        
#         result_path = await engine.generate_voice(test_text)
        
#         if result_path:
#             print(f"เจนสำเร็จ! ไฟล์อยู่ที่: {result_path}")
#         else:
#             print("เจนไม่สำเร็จ")

#     asyncio.run(test())