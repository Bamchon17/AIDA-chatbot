from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import mimetypes
import time
from datetime import datetime
from gtts_engine import ida_gtts_process
import csv

app = Flask(__name__)
CORS(app)  

# --- Path Management ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = CURRENT_DIR  # เพราะ index.html อยู่ที่นี่แล้ว
AUDIO_PATH = os.path.join(CURRENT_DIR, "gtts_respond_week2")

# --- ส่วนการตั้งค่า Log ---
LOG_FOLDER = os.path.join(CURRENT_DIR, 'logs')
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

def save_log(data):
    try:
        # --- 1. เพิ่มการคำนวณ Total Time ---
        latency = data.get('latency', 0)
        duration = data.get('duration', 0)
        total_time = latency + duration

        # --- ส่วนการบันทึก TXT ---
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

        # --- 2. ส่วนการบันทึก CSV (สำหรับส่งงานอาจารย์) ---
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

# --- Frontend ---
@app.route('/')
def serve_index():
    return send_from_directory(STATIC_DIR, 'index.html')  # ✅ ใช้ STATIC_DIR

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_DIR, path)

# --- API ---
@app.route('/api/speech', methods=['POST'])
def receive_speech():
    start_total_time = time.perf_counter()
    try:
        data = request.get_json()
        text = data.get('text', '')
        print(f"🎤 Received: {text}")
        
        result = ida_gtts_process(text, auto_play=False)
        total_latency = time.perf_counter() - start_total_time
        
        save_log({
            'engine_type': 'GTTS',
            'engine': 'gTTS (Translate)',
            'text': text,
            'id': result.get('id', 'UNKNOWN'),
            'latency': total_latency,
            'duration': result.get('duration', 0),
            'rtf': result.get('rtf', 0),
            'script': result.get('script', '')
        })
        
        audio_filename = os.path.basename(result.get('audio_file', '').replace('\\', '/'))
        
        total_time = total_latency + result.get('duration', 0)
        return jsonify({
            'success': True,
            'audio_url': f'/api/audio/{audio_filename}',
            'received_text': text,
            'script': result.get('script', ''),
            'metrics': {
                'tts_latency': result.get('latency', 0),
                'total_backend_latency': total_latency,
                'audio_duration': result.get('duration', 0),
                'rtf': result.get('rtf', 0),
                'total_time': total_time
            }
        })
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<filename>')
def get_audio(filename):
    try:
        full_path = os.path.join(AUDIO_PATH, filename)
        if not os.path.exists(full_path):
            print(f"[DEBUG] ไฟล์ไม่เจอ: {full_path}")
            return "Audio file not found", 404
        mime_type, _ = mimetypes.guess_type(full_path)
        return send_file(full_path, mimetype=mime_type or 'audio/mpeg', as_attachment=False)
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    if not os.path.exists(AUDIO_PATH):
        os.makedirs(AUDIO_PATH)
    print(f"🚀 Server started at http://127.0.0.1:5001")
    app.run(host='127.0.0.1', port=5001, debug=True)