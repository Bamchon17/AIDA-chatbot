import pandas as pd
from gtts import gTTS
import time
import os
from mutagen.mp3 import MP3
import pygame # เล่นเสียงaidaอัตโนมัติ  playing and manipulating sound effects
import random  

# --- path ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(CURRENT_DIR, "processed_dialogue_v2.csv")

# สิ่งที่่เจแปนต้องเอาไปเชื่อม
output_folder = os.path.join(CURRENT_DIR, "gtts_respond_week2")
# อ่าน CSV
df_dialogue = pd.read_csv(
    CSV_PATH, 
    encoding='utf-8', 
    quotechar='"' 
)

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"[DEBUG] Created folder: {output_folder}")


def ida_gtts_process(user_text, auto_play=True):
    # --- ส่วนที่ 1: ค้นหา Script แบบยืดหยุ่น (Flexible Match) ---
    chosen_row = None
    
    # วนลูปเช็คทุกแถวใน CSV
    for index, row in df_dialogue.iterrows():
        # ดึงรายการ Keyword ในแถวนั้นออกมา (เช่น "สวัสดี, Hello" -> ['สวัสดี', 'hello'])
        keywords = [k.strip().lower() for k in str(row['Keyword']).split(',')]
        
        # เช็คว่ามี Keyword คำไหน "ปรากฏอยู่ใน" ประโยคที่ user พูดมาบ้างไหม
        if any(k in user_text.lower() for k in keywords):
            chosen_row = row
            break # เจออันแรกที่ตรงปุ๊บ หยุดหาทันที (ล็อคคำตอบ ไม่สุ่ม)

    if chosen_row is not None:
        script = chosen_row['TTS Script'] 
        msg_id = chosen_row['ID']
        print(f"DEBUG: เจอคำตอบที่ตรงกับ Keyword -> ID: {msg_id}")
    else:
        script = "ขอโทษนะค้า เรื่องนี้พี่ไอด้ายังไม่มีข้อมูลเลยค่ะ ลองสอบถามเรื่องอื่นดูนะ"
        msg_id = "UNKNOWN"

    # --- ส่วนที่ 2: TTS Processing ---
    start_tts = time.perf_counter()
    tts = gTTS(text=script, lang='th')
    output_filename = os.path.join(output_folder, "ida_response.mp3")

    # Interrupt ไอด้า
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

    tts.save(output_filename)
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
