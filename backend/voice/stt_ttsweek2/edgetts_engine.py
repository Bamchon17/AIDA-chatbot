import time 
import pandas as pd
import os
import asyncio
import edge_tts
from mutagen.mp3 import MP3
import pygame
from pythainlp.tokenize import word_tokenize 

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# เช็คชื่อไฟล์ CSV ให้ตรงกับที่คุณแบมใช้จริงนะครับ
CSV_PATH = os.path.join(CURRENT_DIR, "processed_dialogue_v2.csv")
output_folder = os.path.join(CURRENT_DIR, "edgetts_respond_week2")

# อ่าน CSV
df_dialogue = pd.read_csv(CSV_PATH, encoding='utf-8', quotechar='"')

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"[DEBUG] Created folder: {output_folder}")

async def edge_process_voice(user_text, auto_play=True):
    # --- เริ่มจับเวลา Total System ---
    start_total_system = time.perf_counter()
    
    # --- ส่วนที่ 1: ค้นหา Script (Logic Stage) ---
    chosen_row = None
    for index, row in df_dialogue.iterrows():
        keywords = [k.strip().lower() for k in str(row['Keyword']).split(',')]
        if any(k in user_text.lower() for k in keywords):
            chosen_row = row
            break

    if chosen_row is not None:
        script = chosen_row['TTS Script'] 
        msg_id = chosen_row['ID']
        # ดึงค่าจากคอลัมน์ที่คุณแบมต้องการ
        actual_word_count = chosen_row['word_count']
        actual_length_newmm = chosen_row['length_newmm'] 
        print(f"DEBUG: เจอคำตอบที่ตรงกับ Keyword -> ID: {msg_id}")
    else:
        script = "ขอโทษนะคะ เรื่องนี้พี่ไอด้ายังไม่มีข้อมูลเลยค่ะ ลองสอบถามเรื่องอื่นดูนะ"
        msg_id = "UNKNOWN"
        # กรณีไม่เจอใน CSV ให้นับสดๆ เพื่อให้ข้อมูลครบถ้วน
        tokens = word_tokenize(script, engine="newmm")
        actual_word_count = len(tokens)
        actual_length_newmm = len(script.replace(" ", "")) # นับความยาวตัวอักษรไม่รวมช่องว่าง

    logic_latency = time.perf_counter() - start_total_system

    # --- ส่วนที่ 2: สร้างเสียง Edge-TTS ---
    start_tts = time.perf_counter()
    # ป้องกันชื่อไฟล์ซ้ำด้วย Timestamp เล็กน้อยหรือใช้ ID
    output_filename = os.path.join(output_folder, f"{msg_id}_response.mp3")

    communicate = edge_tts.Communicate(
        script, 
        "th-TH-PremwadeeNeural", 
        rate="-3%", 
        pitch="+10Hz"
    )
    
    await communicate.save(output_filename)
    latency = time.perf_counter() - start_tts 

    # --- ส่วนที่ 3: เล่นเสียง ---
    if auto_play:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        try:
            pygame.mixer.music.load(output_filename)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Pygame Play Error: {e}")

    # --- ส่วนที่ 4: วัดผล ---
    audio = MP3(output_filename)
    duration = audio.info.length
    
    # คำนวณความเร็ว (คำนวณจากค่าจริงที่ดึงมา)
    spw = duration / actual_word_count if actual_word_count > 0 else 0
    wpm = (actual_word_count / duration) * 60 if duration > 0 else 0
    rtf = latency / duration if duration > 0 else 0
    
    # เวลารวมตั้งแต่เริ่มหา Keyword จนสร้างไฟล์เสร็จ (ก่อนเริ่มเล่นเสียง)
    total_e2e_latency = time.perf_counter() - start_total_system
    
    # Return ค่าทั้งหมดกลับไปที่ Server เพื่อลง CSV
    return {
       "id": msg_id,
        "word_count": pd.to_numeric(actual_word_count, errors='coerce') or 0,
        "length_newmm": str(actual_length_newmm),
        "script": script,
        "audio_file": output_filename,
        "logic_delay": logic_latency, # เวลาหา Keyword
        "latency": latency, # เวลาสร้างเสียง (ตัวแปรเดิม)
        "duration": duration, # ความยาวเสียง (ตัวแปรเดิม)
        "wpm": wpm, # ความเร็วการพูด
        "spw": spw, # วินาทีต่อคำ
        "rtf": rtf, # Real-time Factor
        "e2e_total_latency": total_e2e_latency # เวลารวมทั้งหมดที่
    }

if __name__ == "__main__":
    # ทดสอบรัน
    text_to_test = "สวัสดีไอด้า"
    result = asyncio.run(edge_process_voice(text_to_test, auto_play=True))
    print("-" * 30)
    print(f"✅ TEST RESULT")
    print(f"ID: {result['id']}")
    print(f"Words: {result['word_count']} | Length: {result['length_newmm']}")
    print(f"Logic Delay: {result['logic_delay']:.4f}s")
    print(f"TTS Latency: {result['latency']:.4f}s")
    print(f"E2E Latency: {result['e2e_total_latency']:.4f}s")
    print(f"WPM: {result['wpm']:.2f}")
    print("-" * 30)