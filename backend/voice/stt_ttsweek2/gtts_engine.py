import pandas as pd
from gtts import gTTS
import time
import os
from mutagen.mp3 import MP3
import pygame
from pythainlp.tokenize import word_tokenize 

# --- path ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(CURRENT_DIR, "processed_dialogue_v2.csv")
output_folder = os.path.join(CURRENT_DIR, "gtts_respond_week2")

# อ่าน CSV
df_dialogue = pd.read_csv(CSV_PATH, encoding='utf-8', quotechar='"')

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"[DEBUG] Created folder: {output_folder}")

def ida_gtts_process(user_text, auto_play=True):
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
        # ดึงค่าจากคอลัมน์ใน CSV
        actual_word_count = chosen_row['word_count']
        actual_length_newmm = chosen_row['length_newmm']
        print(f"DEBUG: เจอคำตอบที่ตรงกับ Keyword -> ID: {msg_id}")
    else:
        script = "ขอโทษนะค้า เรื่องนี้พี่ไอด้ายังไม่มีข้อมูลเลยค่ะ ลองสอบถามเรื่องอื่นดูนะ"
        msg_id = "UNKNOWN"
        # นับคำและตัวอักษรสดๆ กรณีไม่เจอใน CSV
        tokens = word_tokenize(script, engine="newmm")
        actual_word_count = len(tokens)
        actual_length_newmm = len(script.replace(" ", ""))

    logic_latency = time.perf_counter() - start_total_system

    # --- ส่วนที่ 2: TTS Processing (gTTS) ---
    start_tts = time.perf_counter()
    tts = gTTS(text=script, lang='th')
    output_filename = os.path.join(output_folder, f"{msg_id}_gtts_response.mp3")

    # Interrupt เสียงเดิมถ้ามีการเล่นอยู่
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

    tts.save(output_filename)
    latency = time.perf_counter() - start_tts 
    
    # --- ส่วนที่ 3: เล่นเสียง ---
    if auto_play:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        try:
            pygame.mixer.music.load(output_filename)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Pygame Play Error: {e}")

    # --- ส่วนที่ 4: วัดผล ---
    audio = MP3(output_filename)
    duration = audio.info.length
    
    # คำนวณความเร็ว
    spw = duration / actual_word_count if actual_word_count > 0 else 0
    wpm = (actual_word_count / duration) * 60 if duration > 0 else 0
    rtf = latency / duration if duration > 0 else 0
    
    # เวลารวมระบบจนสร้างไฟล์เสร็จ
    total_e2e_latency = time.perf_counter() - start_total_system
    
    # ================= [Return ค่าให้ครบเพื่อลง CSV] =================
    return {
        "id": msg_id,
        "word_count": pd.to_numeric(actual_word_count, errors='coerce') or 0,
        "length_newmm": str(actual_length_newmm),
        "script": script,
        "audio_file": output_filename,
        "logic_delay": logic_latency,
        "latency": latency,
        "duration": duration,
        "wpm": wpm,
        "spw": spw,
        "rtf": rtf,
        "e2e_total_latency": total_e2e_latency
    }

if __name__ == "__main__":
    text_to_test = "สวัสดีจ้าไอด้า"
    print(f"🎤 Testing Input (gTTS): {text_to_test}")
    
    result = ida_gtts_process(text_to_test, auto_play=True) 
    
    print("-" * 35)
    print(f"✅ Result ID: {result['id']}")
    print(f"📊 Words: {result['word_count']} | Length: {result['length_newmm']}")
    print(f"🤖 gTTS Latency: {result['latency']:.4f} s")
    print(f"🚀 Total System Latency: {result['e2e_total_latency']:.4f} s")
    print(f"🎙️ WPM: {result['wpm']:.2f}")
    print("-" * 35)
    
    time.sleep(result['duration'])