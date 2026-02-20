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
        model_name="sentence-transformers/all-MiniLM-L6-v2"
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
        }
        for thai, ascii_name in mapping.items():
            thai_name = thai_name.replace(thai, ascii_name)
        thai_name = re.sub(r'[\u0E00-\u0E7F]', '', thai_name)
        thai_name = re.sub(r'[_\s]+', '_', thai_name).strip('_')
        return thai_name

    # ===============================
    # LOAD DATA
    # ===============================
    def load(self, base_name="combined_embedded"):
        """
        Load FAISS index + chunks + embeddings
        """
        # Match the FAISS ascii filename logic from generate_embeddings.py
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

        # split by delimiter that embedding script used
        self.chunks = [c.strip() for c in raw.split("\n---\n") if c.strip()]

        # Load embeddings if available
        if os.path.exists(pkl_path):
            with open(pkl_path, "rb") as f:
                self.embeddings = pickle.load(f)

        print(f"Loaded {len(self.chunks)} chunks")

    # ===============================
    # SEARCH
    # ===============================
    def search(self, query, top_k=5):
        """
        Search similar chunks
        """

        if self.index is None:
            raise RuntimeError("Call load() first")

        # encode query
        q_vec = self.model.encode([query]).astype("float32")

        # search
        D, I = self.index.search(q_vec, top_k)

        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx < len(self.chunks):
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
        print("\n✅ System ready. ลองพิมพ์คำถามได้เลย (เช่น 'ปี 1 เทอม 1 ต้องทำอะไร', 'สหกิจศึกษาคืออะไร')\n")
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