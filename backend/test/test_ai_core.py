import sys
import os
import json

# ตั้งค่า Path ให้มองเห็นโฟลเดอร์ backend ทั้งหมด
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.ai_core.rag_handler import RAGHandler
from backend.ai_core.llm_interface import LLMInterface
from backend.ai_core.response_formatter import ResponseFormatter

def run_interactive_test():
    print("=" * 60)
    print("🤖 AIDA AI Core Interactive Test (Standalone Mode)")
    print("พิมพ์คำถามเพื่อทดสอบ หรือพิมพ์ 'exit' / 'quit' เพื่อออก")
    print("=" * 60)
    
    try:
        print("[INFO] กำลังโหลดระบบ... (Initializing system components)")
        rag = RAGHandler()
        llm = LLMInterface()
        formatter = ResponseFormatter()
        print("[INFO] ระบบพร้อมใช้งาน! (System Ready)")
    except Exception as e:
        print(f"[ERROR] ระบบขัดข้องตอนเริ่มต้น: {e}")
        return

    while True:
        try:
            print("\n" + "-"*60)
            query = input("🙋‍♂️ คำถามของคุณ: ").strip()
            
            if not query:
                continue
            if query.lower() in ['exit', 'quit']:
                print("[INFO] ปิดระบบทดสอบ. ไว้เจอกันใหม่ครับ!")
                break
                
            # จำลองค่าจาก Zone 1 (Analyzer) ไปก่อน
            mock_intent = "general"
            mock_sentiment = "normal"

            # -----------------------------------------
            # ZONE 2: RAG Handler (ดึงข้อมูล)
            # -----------------------------------------
            print(f"\n[1/3] 🔍 กำลังค้นหาข้อมูลในสมอง FAISS...")
            context = rag.retrieve(query, intent=mock_intent)
            
            if context:
                print(f"      ✅ พบข้อมูลที่เกี่ยวข้อง {len(context)} ชิ้น")
                # แอบดูข้อมูลชิ้นแรกนิดนึงว่าดึงมาถูกหมวดไหม
                preview = context[0].get('text', '')[:120].replace('\n', ' ')
                print(f"      📄 [Top Context Preview]: {preview}...")
            else:
                print(f"      ❌ ไม่พบข้อมูลที่เกี่ยวข้องเลย")

            # -----------------------------------------
            # ZONE 3: LLM Interface (คิดคำตอบ)
            # -----------------------------------------
            print(f"[2/3] 🧠 กำลังส่งให้ Gemini แต่งคำตอบและเลือก Emotion...")
            raw_response = llm.generate_response(
                query=query, 
                retrieval_results=context, 
                intent=mock_intent, 
                sentiment=mock_sentiment
            )

            # -----------------------------------------
            # ZONE 4: Response Formatter (จัดรูปแบบ)
            # -----------------------------------------
            print(f"[3/3] 🛠️ กำลังตรวจสอบความถูกต้องของ JSON...")
            final_response = formatter.format_output(raw_response)

            # -----------------------------------------
            # FINAL OUTPUT
            # -----------------------------------------
            print("\n" + "=" * 60)
            print("✨ AIDA RESPONSE (JSON OUTPUT):")
            print(json.dumps(final_response, indent=2, ensure_ascii=False))
            print("=" * 60)

        except KeyboardInterrupt:
            print("\n[INFO] บังคับปิดระบบ.")
            break
        except Exception as e:
            print(f"\n[ERROR] เกิดข้อผิดพลาดระหว่างทำงาน: {e}")

if __name__ == "__main__":
    run_interactive_test()