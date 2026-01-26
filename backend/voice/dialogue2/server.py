from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import mimetypes
from tts_engine import ida_tts_process

app = Flask(__name__)
# อนุญาต CORS เพื่อความยืดหยุ่น แต่จริงๆ ถ้ารันผ่าน Port เดียวกันจะไม่ค่อยเจอปัญหานี้แล้ว
CORS(app) 

# ดึงตำแหน่งที่ตั้งของไฟล์ server.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ตรวจสอบว่าโฟลเดอร์เสียงชื่อนี้สะกดตรงเป๊ะใน Finder (Mac ซีเรียสเรื่องตัวพิมพ์เล็ก-ใหญ่)
AUDIO_FOLDER_NAME = 'ida_respond_week2'
AUDIO_PATH = os.path.join(BASE_DIR, AUDIO_FOLDER_NAME)

# --- ส่วนของการ Serve ไฟล์หน้าเว็บ ---
@app.route('/')
def serve_index():
    # ตรวจสอบว่า index.html อยู่ในโฟลเดอร์เดียวกับ server.py
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # สำหรับดึงไฟล์ speech.js, style.css ฯลฯ
    return send_from_directory(BASE_DIR, path)

# --- ส่วนของ API ประมวลผลเสียง ---
@app.route('/api/speech', methods=['POST'])
def receive_speech():
    try:
        data = request.get_json()
        text = data.get('text', '')
        print(f"🎤 Received: {text}")
        
        # ส่งไปให้ TTS Engine (ปิด auto_play เพื่อให้ JS เป็นคนเล่นเอง)
        result = ida_tts_process(text, auto_play=False)
        
        # ล้าง Path ที่อาจติดมาจาก Windows (\) ให้เป็นมาตรฐานเดียว
        raw_audio_path = result.get('audio_file', '')
        audio_filename = os.path.basename(raw_audio_path.replace('\\', '/'))
        
        print(f"🎵 Generated Audio: {audio_filename}")
        
        return jsonify({
            'success': True,
            'audio_url': f'/api/audio/{audio_filename}',
            'received_text': text,
            'script': result.get('script', '')
        })
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<filename>')
def get_audio(filename):
    """ส่งไฟล์เสียงให้ Browser โดยระบุ Mimetype ให้ถูกต้องสำหรับ Mac/Safari"""
    try:
        full_path = os.path.join(AUDIO_PATH, filename)
        
        if not os.path.exists(full_path):
            print(f"⚠️ File not found: {full_path}")
            return "Audio file not found", 404
            
        mime_type, _ = mimetypes.guess_type(full_path)
        return send_file(
            full_path, 
            mimetype=mime_type or 'audio/wav',
            as_attachment=False # เพื่อให้เล่นใน Browser ได้ทันที
        )
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    # รันบน 127.0.0.1 เพื่อความเสถียรบน Mac
    print(f"🚀 Server starting at http://127.0.0.1:5001")
    app.run(host='127.0.0.1', port=5001, debug=True)