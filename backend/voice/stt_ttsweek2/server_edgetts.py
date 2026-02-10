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

# --- Path Management ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = CURRENT_DIR 
AUDIO_PATH = os.path.join(CURRENT_DIR, "edgetts_respond_week2")
LOG_FOLDER = os.path.join(CURRENT_DIR, 'logs')

if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

def save_log(data):
    try:
        latency = data.get('latency', 0)
        duration = data.get('duration', 0)
        total_time_classic = latency + duration 

        csv_filename = f"benchmark_{data.get('engine_type', 'voice')}.csv"
        csv_filepath = os.path.join(LOG_FOLDER, csv_filename)
        file_exists = os.path.isfile(csv_filepath)
        
        # --- [ปรับหัวตารางตามลำดับที่คุณแบมต้องการ] ---
        fieldnames = [
            'Timestamp', 'Engine', 'User_Dialogue', 'ID', 
            'word_count', 'length_newmm',      # เพิ่มเข้ามาใหม่
            'Logic_Delay', 'Latency', 'Duration', 'RTF', 
            'Total_Time', 'E2E_Total_Latency', 'WPM', 'SPW', 'TTS_Script'
        ]
        
        with open(csv_filepath, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
                
            writer.writerow({
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Engine': data.get('engine', 'Unknown'),
                'User_Dialogue': data.get('text', ''),
                'ID': data.get('id', 'UNKNOWN'),
                'word_count': data.get('word_count', 0),    # ดึงค่าใหม่
                'length_newmm': data.get('length_newmm', 0), # ดึงค่าใหม่
                'Logic_Delay': f"{data.get('logic_delay', 0):.4f}",
                'Latency': f"{latency:.4f}",
                'Duration': f"{duration:.2f}",
                'RTF': f"{data.get('rtf', 0):.4f}",
                'Total_Time': f"{total_time_classic:.4f}",
                'E2E_Total_Latency': f"{data.get('e2e_total_latency', 0):.4f}",
                'WPM': f"{data.get('wpm', 0):.2f}",
                'SPW': f"{data.get('spw', 0):.4f}",
                'TTS_Script': data.get('script', '')
            })
        print(f"[DEBUG] ✅ Saved Edge Log -> ID: {data.get('id')}")
    except Exception as e:
        print(f"⚠️ Logging Error: {str(e)}")

@app.route('/')
def serve_index():
    return send_from_directory(STATIC_DIR, 'index.html')

# --- [จุดสำคัญที่ผมทำหายไป และใส่กลับมาให้แล้ว] ---
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_DIR, path)

@app.route('/api/speech', methods=['POST'])
def receive_speech():
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        result = asyncio.run(edge_process_voice(text, auto_play=False))
        
        save_log({
            'engine_type': 'edge',
            'engine': 'Edge-TTS (Premwadee)',
            'text': text,
            'id': result.get('id', 'UNKNOWN'),
            'word_count': result.get('word_count', 0),       # ส่งค่าใหม่ไปบันทึก
            'length_newmm': result.get('length_newmm', 0),   # ส่งค่าใหม่ไปบันทึก
            'script': result.get('script', ''),
            'logic_delay': result.get('logic_delay', 0),
            'latency': result.get('latency', 0),
            'duration': result.get('duration', 0),
            'rtf': result.get('rtf', 0),
            'wpm': result.get('wpm', 0),
            'spw': result.get('spw', 0),
            'e2e_total_latency': result.get('e2e_total_latency', 0)
        })
        
        full_audio_path = result.get('audio_file', '')
        audio_filename = os.path.basename(full_audio_path.replace('\\', '/'))

        return jsonify({
            'success': True,
            'audio_url': f'/api/audio/{audio_filename}',
            'received_text': text,
            'script': result.get('script', ''),
            'metrics': {
                'logic_delay': result.get('logic_delay', 0),
                'tts_latency': result.get('latency', 0),
                'duration': result.get('duration', 0),
                'total_time': result.get('latency', 0) + result.get('duration', 0)
            }
        })
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<filename>')
def get_audio(filename):
    try:
        full_path = os.path.join(AUDIO_PATH, filename)
        return send_file(full_path, mimetype='audio/mpeg')
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    if not os.path.exists(AUDIO_PATH): os.makedirs(AUDIO_PATH)
    print(f"[DEBUG] 🚀 Edge Server running on http://127.0.0.1:5002")
    app.run(host='0.0.0.0', port=5002, debug=True)