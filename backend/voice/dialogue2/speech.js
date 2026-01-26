// ตรวจสอบ browser
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    alert('เบราว์เซอร์ของคุณไม่รองรับ Web Speech API\nกรุณาใช้ Chrome หรือ Edge');
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
    const confidence = event.results[0][0].confidence;
    
    transcriptText.textContent = transcript;
    transcriptDiv.classList.add('show');
    statusDiv.textContent = 'กำลังประมวลผล...';
    statusDiv.className = 'success';
    
    try {
        const response = await fetch('http://localhost:5001/api/speech', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: transcript,
                confidence: confidence,
                timestamp: new Date().toISOString()
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // --- เริ่มต้นส่วนที่แก้ไข ---
            if (data.audio_url) {
                console.log('🔊 กำลังโหลดเสียง:', data.audio_url);
                statusDiv.textContent = 'กำลังประมวลผลเสียง...';
                
                // สร้าง Object Audio พร้อมป้องกัน Cache
                const audio = new Audio(`http://localhost:5001${data.audio_url}?t=${new Date().getTime()}`);
                
                // สำหรับ Mac/Safari ต้องโหลดและตั้งค่าก่อนเล่น
                audio.load();
                audio.muted = false; 

                const playPromise = audio.play();

                if (playPromise !== undefined) {
                    playPromise.then(() => {
                        console.log('✅ เล่นเสียงสำเร็จ');
                        statusDiv.textContent = 'กำลังเล่นเสียงตอบกลับ...';
                    }).catch(error => {
                        console.error('❌ Mac/Browser บล็อกการเล่นเสียง:', error);
                        // ถ้าโดนบล็อก จะเปลี่ยนข้อความให้ผู้ใช้คลิกเพื่อเปิดเสียงเอง
                        statusDiv.innerHTML = '🔊 <span style="text-decoration:underline; cursor:pointer;">คลิกตรงนี้เพื่อฟังคำตอบ</span> (Browser บล็อกเสียง)';
                        statusDiv.className = 'success';
                        
                        statusDiv.onclick = () => {
                            audio.play();
                            statusDiv.textContent = 'กำลังเล่นเสียงตอบกลับ...';
                            statusDiv.onclick = null; // คลิกแล้วถอน event ออก
                        };
                    });
                }
                
                audio.onended = () => {
                    console.log('✅ จบการเล่นเสียง');
                    statusDiv.textContent = 'พร้อมใช้งาน - กดปุ่มไมค์เพื่อพูดต่อ';
                    statusDiv.className = '';
                    statusDiv.onclick = null;
                };

                audio.onerror = (e) => {
                    console.error('Audio Error:', e);
                    statusDiv.textContent = 'ไม่สามารถโหลดไฟล์เสียงได้';
                    statusDiv.className = 'error';
                };
            }
        } else {
            statusDiv.textContent = 'Server ตอบกลับผิดพลาด';
            statusDiv.className = 'error';
        }
    } catch (error) {
        console.error('Fetch Error:', error);
        statusDiv.textContent = 'ไม่สามารถเชื่อมต่อ Server (เช็ค Flask)';
        statusDiv.className = 'error';
    }
};

// จัดการ Error ของการรับเสียง
recognition.onerror = (event) => {
    console.error('Recognition Error:', event.error);
    statusDiv.className = 'error';
    statusDiv.textContent = 'เกิดข้อผิดพลาด: ' + event.error;
};

// เมื่อสิ้นสุดการฟัง (ไม่ว่าจะสำเร็จหรือล้มเหลว)
recognition.onend = () => {
    isListening = false;
    micButton.classList.remove('listening');
    console.log('🎤 ไมโครโฟนปิดแล้ว');
};
// --- สิ้นสุดส่วนที่แก้ไข ---