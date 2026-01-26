// ตรวจสอบว่า browser รองรับ Web Speech API หรือไม่
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    alert('เบราว์เซอร์ของคุณไม่รองรับ Web Speech API\nกรุณาใช้ Chrome หรือ Edge');
}

// สร้าง recognition object
const recognition = new SpeechRecognition();
recognition.lang = 'th-TH'; 
recognition.continuous = false; // หยุดฟังอัตโนมัติเมื่อจบประโยค
recognition.interimResults = false; // ไม่ต้องการผลลัพธ์ระหว่างพูด

// ดึง DOM elements
const micButton = document.getElementById('micButton');
const statusDiv = document.getElementById('status');
const transcriptDiv = document.getElementById('transcript');
const transcriptText = document.getElementById('transcriptText');

let isListening = false;

// funcเริ่มเมื่อกดปุ่มไมค์
micButton.addEventListener('click', () => {
    if (isListening) {
        recognition.stop();
    } else {
        recognition.start();
    }
});

// funcเริ่มหลังจากกดปุ่มไมค์
recognition.onstart = () => {
    isListening = true;
    micButton.classList.add('listening');
    statusDiv.textContent = 'กำลังฟัง...';
    statusDiv.className = 'listening';
    console.log('Started listening...');
};

// ฃได้รับผลลัพธ์
recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript;
    const confidence = event.results[0][0].confidence;
    
    console.log('=================================');
    console.log('Transcript:', transcript);
    console.log('Confidence:', (confidence * 100).toFixed(2) + '%');
    console.log('=================================');
    
    // แสดงผลบนหน้าเว็บ
    transcriptText.textContent = transcript;
    transcriptDiv.classList.add('show');
    statusDiv.textContent = 'กำลังสร้างเสียงตอบกลับ...';
    statusDiv.className = 'success';
    
    // ส่งข้อมูลไปยัง backend server.py
    try {
        const response = await fetch('http://localhost:5000/api/speech', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: transcript,
                confidence: confidence,
                timestamp: new Date().toISOString()
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Server response:', data);
            
            // เล่นเสียงที่ได้จาก TTS
            if (data.audio_url) {
                console.log('Playing TTS audio...');
                statusDiv.textContent = 'กำลังเล่นเสียงตอบกลับ...';
                
                const audio = new Audio('http://localhost:5000' + data.audio_url);
                
                audio.onended = () => {
                    console.log('✅ Audio playback finished');
                    statusDiv.textContent = 'พร้อมใช้งาน - กดปุ่มไมค์เพื่อพูดต่อ';
                    statusDiv.className = '';
                };
                
                audio.onerror = (e) => {
                    console.error('Error playing audio:', e);
                    statusDiv.textContent = 'เกิดข้อผิดพลาดในการเล่นเสียง';
                    statusDiv.className = 'error';
                };
                
                audio.play();
            }
        } else {
            console.error('Server error:', response.status);
            statusDiv.textContent = 'เกิดข้อผิดพลาดจาก server';
        }
    } catch (error) {
        console.log('Backend error:', error.message);
        statusDiv.textContent = 'ไม่สามารถเชื่อมต่อ server';
    }
};

// เมื่อเกิดข้อผิดพลาด
recognition.onerror = (event) => {
    console.error('Error:', event.error);
    
    let errorMessage = 'เกิดข้อผิดพลาด';
    
    switch(event.error) {
        case 'no-speech':
            errorMessage = 'ไม่พบเสียง กรุณาลองใหม่';
            break;
        case 'audio-capture':
            errorMessage = 'ไม่พบไมโครโฟน';
            break;
        case 'not-allowed':
            errorMessage = 'กรุณาอนุญาตการใช้ไมโครโฟน';
            break;
    }
    
    statusDiv.textContent = errorMessage;
    statusDiv.className = 'error';
};

// เมื่อหยุดฟัง
recognition.onend = () => {
    isListening = false;
    micButton.classList.remove('listening');
    
    if (!statusDiv.classList.contains('success') && !statusDiv.classList.contains('error')) {
        statusDiv.textContent = 'กดปุ่มไมค์เพื่อเริ่มพูด';
        statusDiv.className = '';
    }
    
    console.log('Stopped listening');
};
