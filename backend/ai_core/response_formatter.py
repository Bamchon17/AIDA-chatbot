class ResponseFormatter:
    @staticmethod
    def format_output(llm_response):
        """
        ตรวจสอบและจัดรูปแบบ JSON ขั้นสุดท้าย
        เพื่อป้องกันไม่ให้ AI ส่งค่า Emotion หรือโครงสร้างแปลกๆ ออกไป
        """
        # โครงสร้างพื้นฐานกรณีเกิดข้อผิดพลาด
        default_response = {
            "display_text": "ขออภัยค่ะ ระบบประมวลผลขัดข้อง โปรดลองใหม่อีกครั้งนะคะ",
            "speech_text": "ขออภัยค่ะ ระบบประมวลผลขัดข้อง",
            "emotion": "Curious",
            "response_metadata": {
                "data_type": "logic",
                "confidence_score": 0.0
            }
        }

        # ถ้าส่งมาไม่ใช่ Dictionary ให้ตีกลับเป็น Default
        if not isinstance(llm_response, dict):
            return default_response

        # ตรวจสอบและบังคับค่า Emotion ให้อยู่ใน 5 สถานะที่กำหนด (ตัวพิมพ์ใหญ่ตัวแรกเสมอ)
        valid_emotions = ["Normal", "Talking","Curious"]
        emotion_raw = str(llm_response.get("emotion", "Normal")).strip().capitalize()
        final_emotion = emotion_raw if emotion_raw in valid_emotions else "Normal"

        # ประกอบร่าง JSON ขั้นสุดท้าย
        cleaned_response = {
            "display_text": llm_response.get("display_text", default_response["display_text"]),
            "speech_text": llm_response.get("speech_text", default_response["speech_text"]),
            "emotion": final_emotion,
            "response_metadata": llm_response.get("response_metadata", default_response["response_metadata"])
        }
        
        return cleaned_response