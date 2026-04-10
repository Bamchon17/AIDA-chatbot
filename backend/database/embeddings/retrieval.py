import os
import faiss
import pickle
import re
import numpy as np
from sentence_transformers import SentenceTransformer


class Retriever:
    def __init__(
        self,
        embedding_dir=r"C:\Graduate Project\AIDA-chatbot\backend\database\embeddings\output_embeddings",
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" # เปลี่ยนเป็นโมเดล Multilingual
    ):
        """
        embedding_dir: folder that contains .faiss / .pkl / chunk files
        model_name: embedding model
        """

        self.embedding_dir = embedding_dir
        self.model = SentenceTransformer(model_name)

        self.index = None
        self.chunks = None
        self.embeddings = None

    def _romanize_filename(self, thai_name):
        """Convert Thai filename to ASCII version to match how FAISS was saved in generate_embeddings.py"""
        mapping = {
            "ค่าเทอม": "fees", "รายชื่ออาจารย์": "teachers", "บริษัท": "companies",
            "บริษัทMOU": "com_mou", "สหกิจ": "co-op", "สาขา": "department",
            "วิชา": "course", "อจ": "teacher", "อาจารย์": "teacher", "mockup": "mockup",
            "ค่า": "fees", "เทอม": "term", "รายชื่อ": "list", "เพื่อการศึกษา": "education",
            "degreeplan": "degreeplan",  # ต้องอยู่ก่อน mapping ที่อาจตัดคำนี้ออก
        }
        # ตรวจ degreeplan ก่อน เพราะชื่อเป็น ASCII อยู่แล้ว ไม่ต้องแปลง
        if thai_name.lower().startswith("degreeplan"):
            return thai_name  # คืนตรงๆ เพราะไม่มีอักษรไทย
        for thai, ascii_name in mapping.items():
            thai_name = thai_name.replace(thai, ascii_name)
        thai_name = re.sub(r'[\u0E00-\u0E7F]', '', thai_name)
        thai_name = re.sub(r'[_\s]+', '_', thai_name).strip('_')
        return thai_name

    # ===============================
    # 1. QUERY ROUTER (ตัวสับรางคำถาม)
    # ===============================
    def detect_category(self, query):
        """ดักจับ Keyword ในคำถาม เพื่อเจาะจงหมวดหมู่ที่จะค้นหา"""
        q = query.lower()

        if any(word in q for word in ["อาจารย์", "อจ", "ผู้สอน", "ดร.", "รศ.", "ผศ.", "สอน"]):
            return "[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]"

        elif any(word in q for word in ["ค่าเทอม", "จ่าย", "กยศ", "กู้", "กี่บาท", "ค่าใช้จ่าย", "แพง"]):
            return "[หมวดหมู่: ค่าเทอมและการเงิน]"

        elif any(word in q for word in ["สหกิจ", "ฝึกงาน", "co-op", "สถานที่ฝึกงาน"]):
            return "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]"

        elif any(word in q for word in ["วิชา", "เรียนอะไร", "รหัสวิชา", "course", "หน่วยกิต"]):
            if "สหกิจ" not in q:
                return "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]"

        elif any(word in q for word in ["แผนการเรียน", "ปี 1", "ปี 2", "ปี 3", "ปี 4",
                                        "เทอม 1", "เทอม 2", "รุ่น", "ปีการศึกษา",
                                        "2565", "2566", "2567", "2568"]):
            if "ค่าเทอม" not in q and "จ่าย" not in q:
                # ถ้าระบุปีการศึกษาชัดเจน ให้ return tag ที่มีปีด้วย
                year_match = re.search(r'(25\d{2})', q)
                if year_match:
                    return f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี{year_match.group(1)}]"
                return "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร]"

        elif any(word in q for word in ["สาขา", "ภาควิชา", "หลักสูตร", "ปริญญา", "จบแล้วทำอะไร", "อาชีพ"]):
            return "[หมวดหมู่: ข้อมูลสาขาวิชา]"

        elif any(word in q for word in ["บริษัท", "mou", "พาร์ทเนอร์", "พันธมิตร"]):
            return "[หมวดหมู่: เครือข่ายบริษัท/MOU]"

        return None

    # ===============================
    # LOAD DATA
    # ===============================
    def load(self, base_name="combined_embedded"):
        """
        Load FAISS index + chunks + embeddings
        """
        ascii_name = self._romanize_filename(base_name)
        
        faiss_path = os.path.join(self.embedding_dir, f"{ascii_name}.faiss")
        pkl_path = os.path.join(self.embedding_dir, f"{base_name}.pkl")
        chunk_path = os.path.join(self.embedding_dir, f"{base_name}_chunk.txt")

        print("Loading from:", self.embedding_dir)

        if not os.path.exists(faiss_path):
            raise FileNotFoundError(f"Missing FAISS file: {faiss_path}")

        if not os.path.exists(chunk_path):
            raise FileNotFoundError(f"Missing chunk text file: {chunk_path}")

        # Load FAISS index
        self.index = faiss.read_index(faiss_path)

        # Load chunks
        with open(chunk_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        self.chunks = [c.strip() for c in raw.split("\n---\n") if c.strip()]

        # Load embeddings if available
        if os.path.exists(pkl_path):
            with open(pkl_path, "rb") as f:
                self.embeddings = pickle.load(f)

        print(f"Loaded {len(self.chunks)} chunks")

    # ===============================
    # SEARCH WITH METADATA FILTERING
    # ===============================
    def search(self, query, top_k=5):
        """
        Search similar chunks
        """
        if self.index is None:
            raise RuntimeError("Call load() first")

        # 1. แปลงคำถามเป็น Vector
        q_vec = self.model.encode([query]).astype("float32")
        
        # 2. ตรวจสอบหมวดหมู่
        target_category = self.detect_category(query)

        # 3. โหมดกรองหมวดหมู่ขั้นเด็ดขาด (Smart Router)
        if target_category and self.embeddings is not None:
            print(f"\n🔍 [ROUTER ACTIVE] กำลังค้นหาเฉพาะ: {target_category}")
            valid_indices = [i for i, chunk in enumerate(self.chunks) if target_category in chunk]

            # ถ้า tag มีปีระบุแต่หาไม่เจอ ให้ลอง fallback ไปที่ tag กลาง (ไม่มีปี)
            if not valid_indices and " ปี" in target_category:
                base_category = target_category.split(" ปี")[0] + "]"
                print(f"   ไม่เจอ tag เฉพาะปี ลอง fallback: {base_category}")
                valid_indices = [i for i, chunk in enumerate(self.chunks) if base_category in chunk]

            if valid_indices:
                filtered_embeddings = self.embeddings[valid_indices]
                distances = np.linalg.norm(filtered_embeddings - q_vec, axis=1)
                best_relative_idx = np.argsort(distances)[:top_k]

                results = []
                for idx in best_relative_idx:
                    original_idx = valid_indices[idx]
                    results.append({
                        "score": float(distances[idx]),
                        "text": self.chunks[original_idx]
                    })
                return results
            # valid_indices ว่างเปล่าจริงๆ → fallback ไป FAISS ด้านล่าง
            print("   ไม่เจอ chunk ที่ตรง tag → fallback ไป FAISS global search")

        # 4. โหมดปกติ (ค้นหาทุกไฟล์)
        if target_category is None:
            print("\n🌐 [ROUTER INACTIVE] ค้นหาจากฐานข้อมูลรวมทั้งหมด")

        D, I = self.index.search(q_vec, top_k)

        results = []
        for dist, idx in zip(D[0], I[0]):
            if 0 <= idx < len(self.chunks):  # ป้องกัน FAISS คืน idx=-1 เมื่อหาไม่พอ
                results.append({
                    "score": float(dist),
                    "text": self.chunks[idx]
                })

        return results


# ===============================
# TEST MODE
# ===============================
if __name__ == "__main__":

    r = Retriever()

    try:
        # โหลด combined embeddings
        r.load("combined_embedded")
        print("\n✅ System ready. ลองพิมพ์คำถามได้เลย (เช่น 'ค่าเทอมปี 1', 'อาจารย์ที่เชี่ยวชาญ ML')\n")
    except Exception as e:
        print(f"\n❌ Error loading files: {e}")
        print("Please ensure you have run generate_embeddings.py first.")
        exit(1)

    while True:
        try:
            q = input("ถาม: ")
            if not q.strip():
                break

            results = r.search(q, top_k=5)

            print("\n" + "="*50)
            print("Top results:")
            print("="*50 + "\n")
            
            for i, res in enumerate(results, 1):
                print(f"[{i}] Score (L2 Distance): {res['score']:.4f}")
                
                # Format chunk output to highlight tags
                lines = res["text"].split('\n')
                for line in lines:
                    if line.startswith("[SOURCE:"):
                        print(f"  📍 {line}")
                    elif line.startswith("[หมวดหมู่:"):
                        print(f"  🏷️ {line}")
                    elif line.strip():
                        print(f"    {line}")
                        
                print("-" * 50)
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError during search: {e}")