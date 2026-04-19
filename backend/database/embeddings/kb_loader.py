"""
kb_loader.py — Knowledge Base Loader with Smart Router
Path: backend/database/embeddings/kb_loader.py

แก้ไขจาก version ของโต้:
  - Bug A: range(len) → list ธรรมดา (valid_indices เป็น list ตลอด)
  - Bug B: load_embeddings_pkl() → load_system() เมื่อยังไม่ได้โหลด
  - เพิ่ม year-fallback กลับมา (ตัด ปีXXXX ออกแล้ว retry base tag)
  - force_category=None backward-compatible ครบ
"""

import os
import re
import pickle
import glob
import numpy as np
from database.embeddings.generate_embeddings import EmbeddingProcessor


class KnowledgeBaseLoader:

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        output_dir: str = None
    ):
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "output_embeddings")

        self.processor   = EmbeddingProcessor(model_name=model_name, output_dir=output_dir)
        self.output_dir  = output_dir
        self.index       = None
        self.chunks      = None
        self.embeddings  = None
        self.loaded_name = None

    def load_embeddings_pkl(self, save_name: str) -> np.ndarray:
        pkl_path = os.path.join(self.output_dir, f"{save_name}.pkl")
        if not os.path.exists(pkl_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ embeddings: {pkl_path}")
        with open(pkl_path, "rb") as f:
            return pickle.load(f)

    def load_chunks(self, save_name: str) -> list:
        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")
        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ chunks: {chunks_path}")
        with open(chunks_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        return [c.strip() for c in raw.split("\n---\n") if c.strip()]

    def load_system(self, save_name: str = "combined_embedded", verbose: bool = True):
        """โหลด FAISS + chunks + embeddings เข้า Memory ทั้งก้อนในครั้งเดียว"""
        self.index, self.chunks = self.processor.load_index_and_chunks(save_name)
        self.embeddings  = self.load_embeddings_pkl(save_name)
        self.loaded_name = save_name
        if verbose:
            print(f"✅ System Loaded: {len(self.chunks)} chunks ready.")

    def detect_category(self, query: str):
        """Keyword-based fallback (ใช้เมื่อไม่มี force_category)"""
        q = query.lower()
        if any(w in q for w in ["อาจารย์","อจ","ผู้สอน","ดร.","ดอกเตอร์","รศ.","ผศ.","สอน"]):
            return "[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]"
        if any(w in q for w in ["ค่าเทอม","จ่าย","กยศ","กู้","กี่บาท","ค่าใช้จ่าย",
                                  "ทุน","รับสมัคร","สัมภาษณ์","ผ่อนผัน"]):
            return "[หมวดหมู่: ค่าเทอมและการเงิน]"
        if any(w in q for w in ["สหกิจ","ฝึกงาน","co-op","coop","intern"]):
            return "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]"
        if any(w in q for w in ["บริษัท","mou","พาร์ทเนอร์","พันธมิตร"]):
            return "[หมวดหมู่: เครือข่ายบริษัท/MOU]"
        course_code = re.search(r"[a-zA-Z]{3}\d{3}", q)
        if course_code or any(w in q for w in ["เรียนเกี่ยวกับอะไร","สอนอะไร","คำอธิบายรายวิชา"]):
            return "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]"
        if any(w in q for w in ["วิชา","เรียนอะไร","รหัสวิชา","หน่วยกิต"]):
            if "สหกิจ" not in q:
                return "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]"
        if any(w in q for w in ["แผนการเรียน","โครงสร้างหลักสูตร","degree plan","degreeplan",
                                  "ปี 1","ปี 2","ปี 3","ปี 4","เทอม 1","เทอม 2",
                                  "2565","2566","2567","2568"]):
            if "ค่าเทอม" not in q and "จ่าย" not in q:
                year_match = re.search(r"(25\d{2})", q)
                if year_match:
                    return f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี{year_match.group(1)}]"
                return "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร]"
        if any(w in q for w in ["สาขา","ภาควิชา","หลักสูตร","ปริญญา",
                                  "จบแล้วทำอะไร","อาชีพ","เงินเดือน","career"]):
            return "[หมวดหมู่: ข้อมูลสาขาวิชา]"
        return None

    def search(
        self,
        query: str,
        save_name: str,
        top_k: int = 5,
        force_category=None
    ) -> list:
        """
        Metadata-filtered vector search

        force_category : str | None
            ส่งมา → ใช้ค่านี้ตรงๆ ข้าม detect_category()
            None  → fallback keyword detection (เหมือนเดิม)
        """
        # ── Bug B Fix: โหลด system ครบ ไม่ใช้แค่ pkl ──
        if self.index is None or self.loaded_name != save_name:
            self.load_system(save_name)

        q_vec = self.processor.model.encode([query]).astype("float32")

        # เลือก category
        if force_category is not None:
            target_category = force_category
            print(f"  [KB] force_category: {target_category}")
        else:
            target_category = self.detect_category(query)
            if target_category:
                print(f"  [KB] keyword detect: {target_category}")

        # ── Filtered search ──
        if target_category:
            # Bug A Fix: valid_indices เป็น list ธรรมดา → numpy index ถูกต้อง
            valid_indices = [
                i for i, chunk in enumerate(self.chunks)
                if target_category in chunk
            ]

            # Year fallback: ปีเจาะจงไม่เจอ → ลอง base tag ไม่มีปี
            if not valid_indices and re.search(r" ปี\d{4}\]$", target_category):
                base_cat = re.sub(r" ปี\d{4}", "", target_category)
                print(f"  [KB] ปีไม่เจอ → fallback: {base_cat}")
                valid_indices = [
                    i for i, chunk in enumerate(self.chunks)
                    if base_cat in chunk
                ]

            if valid_indices:
                filtered_emb = self.embeddings[valid_indices]
                distances    = np.linalg.norm(filtered_emb - q_vec, axis=1)
                best_idx     = np.argsort(distances)[:top_k]
                print(f"  [KB] กรองได้ {len(valid_indices)} chunks → top {top_k}")
                return [
                    {
                        "distance": float(distances[i]),
                        "chunk":    self.chunks[valid_indices[i]]
                    }
                    for i in best_idx
                ]

            print(f"  [KB] ไม่พบ chunks ที่ตรง tag → fallback FAISS global search")

        # ── FAISS global search (fallback) ──
        D, I = self.index.search(q_vec, top_k)
        return [
            {"distance": float(D[0][j]), "chunk": self.chunks[I[0][j]]}
            for j in range(len(I[0]))
            if 0 <= I[0][j] < len(self.chunks)
        ]

    def list_available_indexes(self) -> list:
        return [
            os.path.splitext(os.path.basename(f))[0]
            for f in glob.glob(os.path.join(self.output_dir, "*.faiss"))
        ]