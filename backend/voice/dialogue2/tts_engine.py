import pandas as pd
from gtts import gTTS
import time
import os
from mutagen.mp3 import MP3
import pygame # เล่นเสียงเพลงอัตโนมัติ  playing and manipulating sound effects
import random  

CSV_PATH = 'backend/voice/dialogue2/processed_dialogue_v2.csv'
df_dialogue = pd.read_csv(CSV_PATH)

# สร้างโฟลเดอร์ไว้เก็บเสียงที่รันเสร็จเพื่อให้เจแปนดึงไปเล่น อย่าลืมดึงนี้ไปเล่นนะ
output_folder = "ida_respond_week2"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"สร้างโฟลเดอร์สำเร็จที่: {output_folder}")


def ida_tts_process(user_text, auto_play=True):
    # --- ส่วนที่ 1: ค้นหา Script ทั้งหมดที่ตรงกับ Keyword ---
    # ค้นหาทุกแถวที่มี Keyword ตรงกับที่ user พูด
    matches = df_dialogue[df_dialogue['Keyword'].str.contains(user_text, na=False, case=False)]
    
    if not matches.empty:
        # 2. สุ่มเลือกมา 1 แถวจากรายการที่เจอทั้งหมด 
        chosen_row = matches.sample(n=1).iloc[0]
        
        script = chosen_row['TTS Script']
        msg_id = chosen_row['ID']
        print(f"DEBUG: สุ่มได้ ID -> {msg_id}") # ไว้เช็คว่ามันเปลี่ยนเวอร์ชั่นไหม
    else:
        script = "ขอโทษค่ะ ฉันไม่พบคำตอบที่ตรงกับคำถามนี้"
        msg_id = "UNKNOWN"

    # --- ส่วนที่ 2: สร้างเสียง gTTS ---
    start_tts = time.perf_counter()
    tts = gTTS(text=script, lang='th')
    output_filename = os.path.join(output_folder, "ida_response.mp3")

    # Interrupt ไอด้า
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

    tts.save(output_filename) # เซฟไฟล์เสียงที่ gTTS เพิ่งสร้างขึ้นมาสดๆ
    latency = time.perf_counter() - start_tts  # ตอนเชื่อมเจแปนปลิ้นค่านี้มาด้วยนะ
    
    # --- ส่วนที่ 3: เล่นเสียง ---
    if auto_play:
        pygame.mixer.init()
        pygame.mixer.music.load(output_filename)
        pygame.mixer.music.play()

    # --- ส่วนที่ 4: วัดผล ---
    audio = MP3(output_filename)
    duration = audio.info.length
    rtf = latency / duration if duration > 0 else 0 # ตอนเชื่อมเจแปนปลิ้นค่านี้มาด้วยนะ
    
    return {
        "id": msg_id,
        "script": script,
        "audio_file": output_filename, # ส่งไฟล์เสียงนี้ให้เจแปนไปเล่นเอง
        "latency": latency,
        "duration": duration,
        "rtf": rtf
    }

# # ทดสอบรัน (ลองรันหลายๆ รอบเพื่อดูว่ามันสุ่มไหม)
# if __name__ == "__main__":
#     test_input = "สวัสดี" 
#     result = ida_tts_process(test_input)
#     print(f"ID: {result['id']} | ตอบว่า: {result['script'][:30]}...")
    
#     # รอให้เสียงเล่นจบ
#     while pygame.mixer.music.get_busy():
#         time.sleep(0.1)

# # ==========================================
# # วิธีการทดสอบรัน (Mockup)
# # ==========================================
# if __name__ == "__main__":
#     # จำลองสถานการณ์เพื่อนส่งคำว่า "สวัสดี"
#     test_input = "สวัสดี" 
#     print(f"--- เริ่มประมวลผลสำหรับคำว่า: '{test_input}' ---")
    
#     # เรียกใช้ฟังก์ชัน (ตั้ง auto_play=True เพื่อให้เสียงดังทันที)
#     result = ida_tts_process(test_input, auto_play=True)
    
#     print(f"ID: {result['id']}")
#     print(f"บทพูด: {result['script']}")
#     print(f"Latency (เวลาที่ใช้เจนเสียง): {result['latency']:.4f} วินาที")
#     print(f"Audio Duration (ความยาวเสียง): {result['duration']:.4f} วินาที")
#     print(f"RTF: {result['rtf']:.4f}")
    
#     # ประเมินตามหลัก Jakob Nielsen
#     if result['latency'] < 1.0:
#         status = "รวดเร็วมาก (Instant)"
#     elif result['latency'] <= 10.0:
#         status = "ยอมรับได้ (User Attention Limit)"
#     else:
#         status = "ล่าช้าเกินไป (Attention Loss)"
#     print(f"สถานะ UX: {status}")

#     # ปล่อยให้เสียงเล่นไปสักพักก่อนปิดโปรแกรมทดสอบ
#     time.sleep(2)


# ==========================================
# วิธีการทดสอบรัน (ฉบับแก้ไขให้พูดจนจบ)
# ==========================================
# if __name__ == "__main__":
#     test_input = "สวัสดี" 
#     print(f"--- เริ่มประมวลผลสำหรับคำว่า: '{test_input}' ---")
    
#     result = ida_tts_process(test_input, auto_play=True)
    
#     print(f"ID: {result['id']}")
#     print(f"บทพูด: {result['script']}")
    
#     # --- จุดสำคัญ: ต้องรอให้เสียงเล่นจบก่อนโปรแกรมจะปิด ---
#     print("📢 กำลังเล่นเสียง...")
#     while pygame.mixer.music.get_busy():
#         time.sleep(0.1)  # วนลูปเช็คทุกๆ 0.1 วินาทีว่าเสียงยังดังอยู่ไหม
    
#     print("✅ เล่นเสียงจบเรียบร้อย")
#     pygame.mixer.quit()