import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.database.embeddings.kb_loader import KnowledgeBaseLoader

class RAGHandler:
    def __init__(self):
        # โหลดคลาส KnowledgeBaseLoader ซึ่งมีระบบ Smart Router กรองหมวดหมู่ให้แล้ว
        self.kb_loader = KnowledgeBaseLoader()
        self.index_name = "combined_embedded"
        print("[INFO] Loading RAG Handler (Smart Router & FAISS Search)...")

    def retrieve(self, query, intent="general", top_k=5):
        """
        รับคำถามแล้วส่งไปค้นหาในฐานข้อมูล 
        (รับ parameter intent เผื่อไว้ใช้ในอนาคต แต่ตอนนี้ยังไม่ต้องใช้)
        """
        try:
            # ค้นหาผ่าน kb_loader ซึ่งมันจะกรองหมวดหมู่จาก Keyword ให้เราอัตโนมัติ
            results = self.kb_loader.search(
                query=query, 
                save_name=self.index_name, 
                top_k=top_k
            )
            
            if not results:
                return []

            # จัดรูปแบบผลลัพธ์เพื่อส่งต่อให้ LLM
            final_results = []
            for res in results:
                final_results.append({
                    "text": res.get('chunk', ''),
                    "score": res.get('distance', 0.0)
                })
            
            return final_results

        except Exception as e:
            print(f"[RAG Error] Retrieval failed: {e}")
            return []