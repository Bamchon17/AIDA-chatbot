import time 
import pandas as pd
import os
import asyncio
import edge_tts
from mutagen.mp3 import MP3
import pygame

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(CURRENT_DIR, "processed_dialogue_v2.csv")

output_folder = os.path.join(CURRENT_DIR, "edgetts_respond_week2")

# อ่าน CSV
df_dialogue = pd.read_csv(
    CSV_PATH, 
    encoding='utf-8', 
    quotechar='"'
)

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"[DEBUG] Created folder: {output_folder}")


async def edge_process_voice(user_text, auto_play=True):
    chosen_row = None
    for index, row in df_dialogue.iterrows():
        keywords = [k.strip().lower() for k in str(row['Keyword']).split(',')]
        if any(k in user_text.lower() for k in keywords):
            chosen_row = row
            break

    if chosen_row is not None:
        script = chosen_row['TTS Script'] 
        msg_id = chosen_row['ID']
        print(f"DEBUG: เจอคำตอบที่ตรงกับ Keyword -> ID: {msg_id}")
    else:
        script = "ขอโทษนะค่ะ เรื่องนี้พี่ไอด้ายังไม่มีข้อมูลเลยค่ะ ลองสอบถามเรื่องอื่นดูนะ"
        msg_id = "UNKNOWN"

    # --- ส่วนที่ 2: สร้างเสียง Edge-TTS (Neural) ---
    start_tts = time.perf_counter()
    output_filename = os.path.join(output_folder, "ida_response.mp3")

    # Premwadee 
    communicate = edge_tts.Communicate(
        script, 
        "th-TH-PremwadeeNeural", 
        rate="-5%", 
        pitch="+5Hz"
    )
    
    # บันทึกไฟล์แบบ Async
    await communicate.save(output_filename)
    
    latency = time.perf_counter() - start_tts 

    # --- ส่วนที่ 3: เล่นเสียง ---
    if auto_play:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        else:
            pygame.mixer.init()
            
        pygame.mixer.music.load(output_filename)
        pygame.mixer.music.play()

    # --- ส่วนที่ 4: วัดผล ---
    audio = MP3(output_filename)
    duration = audio.info.length
    rtf = latency / duration if duration > 0 else 0
    
    return {
        "id": msg_id,
        "script": script,
        "audio_file": output_filename,
        "latency": latency,
        "duration": duration,
        "rtf": rtf
    }

if __name__ == "__main__":
    text_to_test = "สวัสดีไอด้า"
    result = asyncio.run(edge_process_voice(text_to_test, auto_play=True))
    print(f"Latency: {result['latency']:.4f}s | RTF: {result['rtf']:.4f}")