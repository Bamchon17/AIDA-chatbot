let CURRENT_PORT = '5001';
const BASE_URL = () => `http://localhost:${CURRENT_PORT}`;

function switchEngine(port) {
    CURRENT_PORT = port;
    console.log(`🔄 สลับไปพอร์ต: ${port}`);
    statusDiv.textContent = `สลับเป็น Engine พอร์ต ${port} แล้ว`;
}

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SpeechRecognition) {
    alert('ต้องใช้ Chrome หรือ Edge');
}

const recognition = new SpeechRecognition();
recognition.lang = 'th-TH';
recognition.continuous = false;
recognition.interimResults = false;

const micButton = document.getElementById('micButton');
const statusDiv = document.getElementById('status');
const transcriptDiv = document.getElementById('transcript');
const transcriptText = document.getElementById('transcriptText');

let isListening = false;

micButton.addEventListener('click', () => {
    if (isListening) {
        recognition.stop();
    } else {
        recognition.start();
    }
});

recognition.onstart = () => {
    isListening = true;
    micButton.classList.add('listening');
    statusDiv.textContent = 'กำลังฟัง...';
    statusDiv.className = 'listening';
};

recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript;
    transcriptText.textContent = transcript;
    transcriptDiv.classList.add('show');
    statusDiv.textContent = `กำลังส่งไปพอร์ต ${CURRENT_PORT}...`;
    statusDiv.className = 'loading';

    try {
        const response = await fetch(`${BASE_URL()}/api/speech`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: transcript })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.audio_url) {
                console.log('🔊 Fetching audio:', data.audio_url);
                const audioUrl = `${BASE_URL()}${data.audio_url}?t=${Date.now()}`;
                const audio = new Audio(audioUrl);
                
                // --- แก้ไขส่วนการแสดงผล Metrics ---
                audio.onloadedmetadata = () => {
                    console.log('✅ Audio ready');
                    
                    // ดึงค่ามาเตรียมไว้ (เช็คก่อนว่ามีค่าส่งมาไหม ถ้าไม่มีให้เป็น 0)
                    const lat = data.metrics.total_backend_latency || 0;
                    const dur = data.metrics.audio_duration || 0;
                    const total = data.metrics.total_time || (lat + dur); // ถ้าลืมส่ง total_time มา ก็บวกสดตรงนี้เลย
                    
                    // ปรับข้อความโชว์หน้าเว็บให้ครบถ้วน
                    statusDiv.textContent = `กำลังเล่น... (Latency: ${lat.toFixed(3)}s | Total: ${total.toFixed(2)}s)`;
                    
                    audio.play().catch(e => {
                        console.error('Autoplay blocked:', e);
                        statusDiv.textContent = '❌ Autoplay blocked - กดไมค์อีกครั้ง';
                    });
                };

                audio.onended = () => {
                    statusDiv.textContent = `กำลังเล่น... (Lat: ${lat.toFixed(3)}s | Dur: ${dur.toFixed(2)}s | Total: ${total.toFixed(2)}s)`;
                    statusDiv.className = '';
                };

                audio.onerror = (e) => {
                    console.error('Audio error:', e);
                    statusDiv.textContent = '❌ Error loading audio';
                    statusDiv.className = 'error';
                };
            }
        } else {
            statusDiv.textContent = `❌ พอร์ต ${CURRENT_PORT} ไม่ตอบสนอง`;
            statusDiv.className = 'error';
        }
    } catch (error) {
        console.error('Fetch error:', error);
        statusDiv.textContent = `❌ ไม่สามารถเชื่อมต่อพอร์ต ${CURRENT_PORT}`;
        statusDiv.className = 'error';
    }
};

recognition.onerror = (event) => {
    statusDiv.className = 'error';
    statusDiv.textContent = '❌ Error: ' + event.error;
};

recognition.onend = () => {
    isListening = false;
    micButton.classList.remove('listening');
};