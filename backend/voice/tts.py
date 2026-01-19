# backend/voice/tts.py
#Microsoft Edge
import edge_tts
import asyncio

class VoiceEngine:
    def __init__(self):
        # รายชื่อเสียงที่เลือกไว้ (สามารถเพิ่มได้)
        self.voices = {
            "female_soft": "th-TH-PremwadeeNeural",
            "male_formal": "th-TH-NiwatNeural"
        }

    async def generate_edge(self, text, voice_key="female_soft", output_path="output.mp3"):
        voice = self.voices.get(voice_key, self.voices["female_soft"])
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path

    # สามารถเพิ่ม method สำหรับ Google TTS หรือค่ายอื่นๆ ได้ที่นี่