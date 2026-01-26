from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
import os
from tts_engine import ida_tts_process

app = Flask(__name__)
CORS(app)  # อนุญาตให้เรียกใช้จาก frontend

@app.route('/api/speech', methods=['POST'])
def receive_speech():
    try:
        data = request.get_json()
        text = data.get('text', '')
        confidence = data.get('confidence', 0)
        timestamp = data.get('timestamp', '')
        
        # แสดงผลใน VS Code terminal
        print('=' * 50)
        print('RECEIVED SPEECH FROM CLIENT')
        print('=' * 50)
        print(f'Text: {text}')
        print(f'Confidence: {confidence * 100:.2f}%')
        print(f'Timestamp: {timestamp}')
        print('=' * 50)
        
        # ใช้ TTS Engine เพื่อค้นหา keyword และสร้างเสียง
        print('Processing with TTS Engine...')
        result = ida_tts_process(text, auto_play=False)
        
        print(f'Matched ID: {result["id"]}')
        print(f'Script: {result["script"]}')
        print(f'Latency: {result["latency"]:.4f}s')
        print(f'🎵 Duration: {result["duration"]:.4f}s')
        print(f'📊 RTF: {result["rtf"]:.4f}')
        print('=' * 50)
        
        # ส่ง URL ของไฟล์เสียงกลับไปที่ speech.js
        audio_filename = os.path.basename(result['audio_file'])
        audio_url = f'/api/audio/{audio_filename}'
        
        return jsonify({
            'success': True,
            'message': 'Speech received and TTS generated',
            'received_text': text,
            'matched_id': result['id'],
            'script': result['script'],
            'audio_url': audio_url,
            'latency': result['latency'],
            'duration': result['duration'],
            'rtf': result['rtf'],
            'server_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f'Error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """ส่งไฟล์เสียงกลับไปให้ frontend"""
    try:
        # ใช้โฟลเดอร์จาก tts_engine
        audio_path = os.path.join('ida_respond_week2', filename)
        return send_file(audio_path, mimetype='audio/mpeg')
    except Exception as e:
        print(f'Error sending audio: {str(e)}')
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    print('🚀 Starting Flask server...')
    print('📡 Listening on http://localhost:5000')
    print('Press Ctrl+C to stop')
    app.run(host='0.0.0.0', port=5000, debug=True)
