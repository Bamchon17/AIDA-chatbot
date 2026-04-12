class ResponseFormatter:

    # ── Canned responses ────────────────────────────────────────────────────────
    CANNED = {
        "toxic": {
            "display_text": "หนูรับได้เฉพาะคำถามที่สุภาพนะคะ ลองถามใหม่ได้เลยค่ะ 😊",
            "speech_text":  "หนูรับได้เฉพาะคำถามที่สุภาพนะคะ ลองถามใหม่ได้เลยค่ะ",
            "emotion":      "Curious",   # ยังไม่ตอบได้ → Curious
        },
        "greeting": {
            "display_text": "สวัสดีค่ะ! หนู AIDA น้องผู้ช่วยของคณะ AI & Data Science ค่ะ มีอะไรให้หนูช่วยไหมคะ?",
            "speech_text":  "สวัสดีค่ะ หนู AIDA น้องผู้ช่วยของคณะ เอไอ แอนด์ ดาต้าไซนส์ ค่ะ มีอะไรให้หนูช่วยไหมคะ",
            "emotion":      "Normal",    # ยังไม่มีใครพูดอะไร → Normal
        },
        "out_of_scope": {
            "display_text": "ขอโทษนะคะ คำถามนี้อยู่นอกเหนือขอบเขตที่หนูรู้ค่ะ ลองถามเกี่ยวกับคณะ AI & Data Science ดูนะคะ",
            "speech_text":  "ขอโทษนะคะ คำถามนี้อยู่นอกเหนือขอบเขตที่หนูรู้ค่ะ",
            "emotion":      "Curious",   # ตอบคำถามไม่ได้ → Curious
        },
        "report_issue": {
            "display_text": "ขอโทษที่มีปัญหานะคะ ลองติดต่อเจ้าหน้าที่สาขาโดยตรง หรือแจ้งผ่านช่องทางอีเมลของคณะได้เลยค่ะ",
            "speech_text":  "ขอโทษที่มีปัญหานะคะ ลองติดต่อเจ้าหน้าที่สาขาโดยตรงได้เลยค่ะ",
            "emotion":      "Talking",   # กำลังให้ข้อมูลช่องทาง → Talking
        },
    }

    # ── Clarification 3 ขั้น สำหรับ curriculum ──────────────────────────────
    # ขั้น 1: ไม่มีปีหลักสูตร → ถามปี
    CLARIFY_YEAR = {
        "display_text": (
            "หนูอยากตอบให้ถูกต้องเลยค่ะ 😊\n"
            "รบกวนระบุปีหลักสูตรด้วยได้ไหมคะ?\n"
            "• หลักสูตร ปี 2565\n"
            "• หลักสูตร ปี 2566\n"
            "• หลักสูตร ปี 2567\n"
            "• หลักสูตร ปี 2568"
        ),
        "speech_text": (
            "หนูอยากตอบให้ถูกต้องค่ะ "
            "รบกวนระบุปีหลักสูตรด้วยได้ไหมคะ เช่น หลักสูตรปี 2567 หรือ 2568 คะ"
        ),
        "emotion": "Curious",
    }

    # ขั้น 2: มีปีแล้ว แต่ไม่มีรุ่น → ถามรุ่น
    CLARIFY_GEN = {
        "display_text": (
            "ขอถามเพิ่มเติมอีกนิดนึงนะคะ 😊\n"
            "น้องเป็นรุ่นไหนคะ?\n"
            "• รุ่น 1/1 (เข้าเทอม 1)\n"
            "• รุ่น 1/2 (เข้าเทอม 2)\n"
            "• รุ่น 2 (เข้าภาคฤดูร้อน)"
        ),
        "speech_text": (
            "ขอถามเพิ่มเติมอีกนิดนะคะ น้องเป็นรุ่นไหนคะ "
            "รุ่น 1/1 รุ่น 1/2 หรือ รุ่น 2 คะ"
        ),
        "emotion": "Curious",
    }

    # ขั้น 3: มีปีและรุ่นแล้ว แต่ไม่มีแผน → ถามแผน
    CLARIFY_PLAN = {
        "display_text": (
            "เกือบครบแล้วค่ะ 😊\n"
            "น้องเรียนแผนไหนคะ?\n"
            "• แผนปกติ\n"
            "• แผนสหกิจศึกษา"
        ),
        "speech_text": (
            "เกือบครบแล้วค่ะ น้องเรียนแผนปกติ หรือ แผนสหกิจศึกษาคะ"
        ),
        "emotion": "Curious",
    }

    # backward-compat alias
    CURRICULUM_CLARIFY = CLARIFY_YEAR

    # ── ลดเหลือ 3 states เท่านั้น ────────────────────────────────────────────
    VALID_EMOTIONS = {"Normal", "Curious", "Talking"}

    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def handle_no_retrieval(intent_result: dict) -> dict | None:
        """
        คืน response dict ทันทีใน 2 กรณี:
          1. Canned intent (toxic / greeting / out_of_scope / report_issue)
          2. Curriculum ไม่ระบุปี → ถามกลับ

        คืน None → ให้ผ่านไป RAG + LLM ตามปกติ
        """
        label    = intent_result.get("intent", {}).get("label", "")
        entities = intent_result.get("entities", {})

        # กรณี 1: Canned
        if label in ResponseFormatter.CANNED:
            canned = ResponseFormatter.CANNED[label]
            return {
                "display_text": canned["display_text"],
                "speech_text":  canned["speech_text"],
                "emotion":      canned["emotion"],
                "response_metadata": {
                    "intent":           label,
                    "data_type":        "logic",
                    "confidence_score": 1.0,
                    "is_canned":        True,
                    "is_clarification": False,
                }
            }

        # กรณี 2: Curriculum → 3-step clarification
        # ขั้น 1: ไม่มีปี
        if label == "curriculum_info" and not entities.get("curriculum_year", ""):
            c = ResponseFormatter.CLARIFY_YEAR
            return {
                "display_text": c["display_text"],
                "speech_text":  c["speech_text"],
                "emotion":      c["emotion"],
                "response_metadata": {
                    "intent": label, "data_type": "logic",
                    "confidence_score": 1.0,
                    "is_canned": True, "is_clarification": True,
                    "clarification_step": "year",
                }
            }
        # ขั้น 2: มีปีแล้ว แต่ไม่มีรุ่น
        if label == "curriculum_info" and entities.get("curriculum_year") \
                and not entities.get("generation", ""):
            c = ResponseFormatter.CLARIFY_GEN
            return {
                "display_text": c["display_text"],
                "speech_text":  c["speech_text"],
                "emotion":      c["emotion"],
                "response_metadata": {
                    "intent": label, "data_type": "logic",
                    "confidence_score": 1.0,
                    "is_canned": True, "is_clarification": True,
                    "clarification_step": "generation",
                }
            }
        # ขั้น 3: มีปีและรุ่นแล้ว แต่ไม่มีแผน
        if label == "curriculum_info" and entities.get("curriculum_year") \
                and entities.get("generation") \
                and not entities.get("plan", ""):
            c = ResponseFormatter.CLARIFY_PLAN
            return {
                "display_text": c["display_text"],
                "speech_text":  c["speech_text"],
                "emotion":      c["emotion"],
                "response_metadata": {
                    "intent": label, "data_type": "logic",
                    "confidence_score": 1.0,
                    "is_canned": True, "is_clarification": True,
                    "clarification_step": "plan",
                }
            }

        return None

    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def format_output(llm_response: dict | None, intent_result: dict) -> dict:
        """
        จัดรูปแบบ JSON ขั้นสุดท้าย
        - บังคับ emotion ให้อยู่ใน {Normal, Curious, Talking} เท่านั้น
        - Happy / Encouraging → แปลงเป็น Talking อัตโนมัติ
        """
        intent_info = intent_result.get("intent", {})
        entities    = intent_result.get("entities", {})
        label       = intent_info.get("label", "general")
        confidence  = intent_info.get("confidence", 0.0)

        default_response = {
            "display_text": "ขออภัยค่ะ ระบบประมวลผลขัดข้อง โปรดลองใหม่อีกครั้งนะคะ",
            "speech_text":  "ขออภัยค่ะ ระบบประมวลผลขัดข้อง",
            "emotion":      "Curious",
            "response_metadata": {
                "intent":           label,
                "data_type":        "logic",
                "confidence_score": 0.0,
                "entities":         entities,
                "is_canned":        False,
                "is_clarification": False,
            }
        }

        if not isinstance(llm_response, dict):
            return default_response

        # ── Emotion mapping (3 states) ──────────────────────────────────────
        # LLM อาจยังส่ง Happy / Encouraging มา → map ให้เหมาะสม
        EMOTION_MAP = {
            "Normal":      "Normal",
            "Talking":     "Talking",
            "Curious":     "Curious",
            "Happy":       "Normal",       # ทักทายยิ้มแย้ม → Normal
            "Encouraging": "Talking",      # ให้กำลังใจ/แนะนำ → Talking
        }
        raw_emotion   = str(llm_response.get("emotion", "Normal")).strip().capitalize()
        final_emotion = EMOTION_MAP.get(raw_emotion, "Normal")

        raw_meta = llm_response.get("response_metadata", {})
        return {
            "display_text": llm_response.get("display_text", default_response["display_text"]),
            "speech_text":  llm_response.get("speech_text",  default_response["speech_text"]),
            "emotion":      final_emotion,
            "response_metadata": {
                "intent":           label,
                "data_type":        raw_meta.get("data_type", "logic"),
                "confidence_score": raw_meta.get("confidence_score", confidence),
                "entities":         entities,
                "is_canned":        False,
                "is_clarification": False,
            }
        }