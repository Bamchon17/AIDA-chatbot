from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import csv
import mimetypes
import time
import asyncio
from datetime import datetime
from edgetts_engine import edge_process_voice
app = Flask(__name__)
CORS(app) 

# --- การจัดการเส้นทางไฟล์ (Path Management) -----
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = CURRENT_DIR  # เพราะ index.html อยู่ที่นี่แล้ว
AUDIO_PATH = os.path.join(CURRENT_DIR, "edgetts_respond_week2")

# --- ส่วนการตั้งค่า Log ---
LOG_FOLDER = os.path.join(CURRENT_DIR, 'logs')
print(f"[DEBUG] LOG_FOLDER: {LOG_FOLDER}")
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)
    print("[DEBUG] สร้าง LOG_FOLDER ใหม่เรียบร้อย")

def save_log(data):
    try:
          # --- 1. เพิ่มการคำนวณ Total Time ---
        latency = data.get('latency', 0)
        duration = data.get('duration', 0)
        total_time = latency + duration

        # --- ส่วนการบันทึก TXT (สำหรับอ่านไวๆ) ---
        txt_filename = f"log_{data.get('engine_type', 'voice')}_{datetime.now().strftime('%Y-%m-%d')}.txt"
        txt_filepath = os.path.join(LOG_FOLDER, txt_filename)
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        log_entry = (
            f"[{timestamp}] User: {data.get('text', '')}\n"
            f"           ID: {data.get('id', 'UNKNOWN')} | Latency: {data.get('latency', 0):.4f}s | Duration: {data.get('duration', 0):.2f}s\n"
            f"           RTF: {data.get('rtf', 0):.4f} | Script: {data.get('script', '')}\n"
            f"{'-'*60}\n"
        )
        with open(txt_filepath, "a", encoding="utf-8") as f:
            f.write(log_entry)

        # --- 2. ส่วนการบันทึก CSV  ---
        csv_filename = f"benchmark_{data.get('engine_type', 'voice')}.csv"
        csv_filepath = os.path.join(LOG_FOLDER, csv_filename)
        file_exists = os.path.isfile(csv_filepath)
        
        with open(csv_filepath, mode='a', newline='', encoding='utf-8') as f:
            # 1. เพิ่ม Total_Time เข้าไปใน fieldnames
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Engine', 'User_Dialogue', 'ID', 
                'Latency', 'Duration', 'RTF', 'Total_Time', 'TTS_Script'
            ])
            
            if not file_exists:
                writer.writeheader()
                
            # 2. ใส่ค่า total_time ลงในคอลัมน์ใหม่
            writer.writerow({
                'Timestamp': f"{datetime.now().strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M:%S')}",
                'Engine': data.get('engine', 'Unknown'),
                'User_Dialogue': data.get('text', ''),
                'ID': data.get('id', 'UNKNOWN'),
                'Latency': f"{latency:.4f}",
                'Duration': f"{duration:.2f}",
                'RTF': f"{data.get('rtf', 0):.4f}",
                'Total_Time': f"{total_time:.4f}", # บันทึกค่านี้ลงไป
                'TTS_Script': data.get('script', '')
            })
        print(f"[DEBUG] Logged Total_Time: {total_time:.4f}s")
    except Exception as e:
        print(f"⚠️ Logging Error: {str(e)}")

# --- การ Serve หน้าเว็บ (Frontend) ---
@app.route('/')
def serve_index():
    print("[DEBUG] มีคนเข้ามาที่หน้า root '/'")
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    print(f"[DEBUG] ขอไฟล์ static: {path}")
    return send_from_directory(STATIC_DIR, path)

# --- API ประมวลผลเสียง ---
@app.route('/api/speech', methods=['POST'])
def receive_speech():
    start_total_time = time.perf_counter()
    print("[DEBUG] มี request เข้ามาที่ /api/speech")
    
    try:
        data = request.get_json()
        text = data.get('text', '')
        print(f"[DEBUG] ได้รับ text จาก frontend: '{text}'")
        
        print("[DEBUG] เริ่มเรียก edge_process_voice...")
        result = asyncio.run(edge_process_voice(text, auto_play=False))
        print("[DEBUG] edge_process_voice เสร็จแล้ว")
        print(f"[DEBUG] Result จาก engine: {result}")
        
        total_latency = time.perf_counter() - start_total_time
        print(f"[DEBUG] Total backend latency: {total_latency:.4f} วินาที")
        
        save_log({
            'engine_type': 'edge',
            'engine': 'Edge-TTS (Premwadee)',
            'text': text,
            'id': result.get('id', 'UNKNOWN'),
            'latency': total_latency,
            'duration': result.get('duration', 0),
            'rtf': result.get('rtf', 0),
            'script': result.get('script', '')
        })
        
        audio_filename = os.path.basename(result.get('audio_file', '').replace('\\', '/'))
        print(f"[DEBUG] ส่ง audio_url กลับ: /api/audio/{audio_filename}")

        # คำนวณเตรียมไว้ก่อนส่ง
        total_time = total_latency + result.get('duration', 0)
        return jsonify({
            'success': True,
            'audio_url': f'/api/audio/{audio_filename}',
            'received_text': text,
            'script': result.get('script', ''),
            'metrics': {
                'total_backend_latency': total_latency,
                'audio_duration': result.get('duration', 0),
                'total_time': total_time
            }
        })
    except Exception as e:
        print(f"[DEBUG] ❌ API Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<filename>')
def get_audio(filename):
    print(f"[DEBUG] ขอไฟล์เสียง: {filename}")
    try:
        full_path = os.path.join(AUDIO_PATH, filename)
        print(f"[DEBUG] Full path ของไฟล์เสียง: {full_path}")
        print(f"[DEBUG] ไฟล์มีจริงไหม? {os.path.exists(full_path)}")
        
        if not os.path.exists(full_path):
            print("[DEBUG] ไม่เจอไฟล์เสียง!")
            return "Audio file not found", 404
            
        mime_type, _ = mimetypes.guess_type(full_path)
        print(f"[DEBUG] MIME type: {mime_type or 'audio/mpeg'}")
        
        return send_file(full_path, mimetype=mime_type or 'audio/mpeg', as_attachment=False)
    except Exception as e:
        print(f"[DEBUG] Error ส่งไฟล์เสียง: {str(e)}")
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    if not os.path.exists(AUDIO_PATH):
        os.makedirs(AUDIO_PATH)
        print(f"[DEBUG] สร้าง folder AUDIO_PATH ใหม่: {AUDIO_PATH}")
    
    print(f"[DEBUG] 🚀 Server starting at http://127.0.0.1:5002")
    print("[DEBUG] กำลังรัน Flask server...")
    app.run(host='0.0.0.0', port=5002, debug=True)  # เปลี่ยนเป็น 0.0.0.0 เพื่อให้เข้าจาก localhost ได้ชัวร์