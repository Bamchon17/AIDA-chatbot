import re
import os
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer


class EmbeddingProcessor:
    """
    Class to handle text chunking and embedding generation.
    Uses sentence-transformers/all-MiniLM-L6-v2 model for embeddings.
    Saves outputs to Final_output folder.
    """

    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, model_name=None, output_dir=None):
        if model_name is None:
            model_name = self.MODEL_NAME
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "output_embeddings")
            
        self.model = SentenceTransformer(model_name)
        self.output_dir = output_dir
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    # =====================
    # CHUNK FUNCTIONS
    # =====================
    # Note: Removed outdated hardcoded regex chunkers. 
    # Relying on semantic and markdown chunking based on the new Data Prep Guidelines.

    @staticmethod
    def chunk_paragraphs(text, chunk_size=500, overlap=100):
        paragraphs = re.split(r'\n\s*\n', text.strip())
        chunks = []
        buffer = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            if buffer and len(buffer) + len(paragraph) > chunk_size:
                chunks.append(buffer.strip())
                buffer = paragraph
            else:
                if buffer:
                    buffer += "\n\n" + paragraph
                else:
                    buffer = paragraph
        
        if buffer:
            chunks.append(buffer.strip())
        
        return [c for c in chunks if len(c) > 50]

    @staticmethod
    def chunk_markdown_tables(text):
        chunks = []
        sections = re.split(r'^## ', text, flags=re.MULTILINE)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            if '|' not in section: 
                subsections = re.split(r'^### ', section, flags=re.MULTILINE)
                for subsection in subsections:
                    subsection = subsection.strip()
                    if len(subsection) > 30:
                        chunks.append(subsection)
            else:
                if len(section) > 30:
                    chunks.append(section)
        
        return chunks

    @staticmethod
    def chunk_markdown_hierarchy(text):
        chunks = []
        parts = re.split(r'^### ', text, flags=re.MULTILINE)
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            if i > 0:
                part = '### ' + part
            
            if len(part) > 30:
                chunks.append(part)
        
        return chunks

    @staticmethod
    def chunk_markdown_semantic(text, chunk_size=400):
        chunks = []
        heading_pattern = r'^### '
        sections = re.split(heading_pattern, text, flags=re.MULTILINE)
        
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue
            
            if i > 0:
                section = '### ' + section
            
            if '|' in section:
                parts = section.split('\n\n')
                current_chunk = ""
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    if current_chunk and len(current_chunk) + len(part) > chunk_size:
                        chunks.append(current_chunk.strip())
                        current_chunk = part
                    else:
                        if current_chunk:
                            current_chunk += "\n\n" + part
                        else:
                            current_chunk = part
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                paragraphs = section.split('\n\n')
                current_chunk = ""
                
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    
                    if current_chunk and len(current_chunk) + len(para) > chunk_size:
                        chunks.append(current_chunk.strip())
                        current_chunk = para
                    else:
                        if current_chunk:
                            current_chunk += "\n\n" + para
                        else:
                            current_chunk = para
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
        
        return [c for c in chunks if len(c) > 30]

    @staticmethod
    def chunk_by_section(text):
        """
        สำหรับ degree plan files (degreeplan*_clean.txt)
        Split ที่ #### (รุ่น/แผน) แล้วเก็บ breadcrumb ## / ### ไว้ใน header ของแต่ละ chunk
        ผลลัพธ์: 1 chunk = 1 รุ่น + แผน + เทอม + ปีที่ (พร้อม context ครบ)
        """
        chunks = []
        current_h2 = ""
        current_h3 = ""
        current_h4 = ""
        current_body_lines = []

        def flush():
            body = "\n".join(current_body_lines).strip()
            if not body:
                return
            header_parts = []
            if current_h2:
                header_parts.append(current_h2)
            if current_h3:
                header_parts.append(current_h3)
            if current_h4:
                header_parts.append(current_h4)
            chunk = "\n".join(header_parts) + "\n" + body if header_parts else body
            if len(chunk) > 40:
                chunks.append(chunk.strip())

        for line in text.splitlines():
            if line.startswith("#### "):
                flush()
                current_h4 = line
                current_body_lines = []
            elif line.startswith("### "):
                flush()
                current_h3 = line
                current_h4 = ""
                current_body_lines = []
            elif line.startswith("## "):
                flush()
                current_h2 = line
                current_h3 = ""
                current_h4 = ""
                current_body_lines = []
            else:
                current_body_lines.append(line)

        flush()
        return chunks

    # =====================
    # HELPER & EMBEDDING FUNCTIONS
    # =====================

    def _get_context_tag(self, filename):
        """Auto-generate category tag based on filename to prevent Context Confusion"""
        fname = filename.lower()
        # degree plan ต้องตรวจก่อน "วิชา" เพราะชื่อไฟล์ degreeplan*_clean.txt
        if "degreeplan" in fname or "degree_plan" in fname:
            # พยายามดึงปีการศึกษาจากชื่อไฟล์ เช่น degreeplan2568_clean.txt
            import re
            year_match = re.search(r'(25\d{2})', filename)
            year_str = f" ปี{year_match.group(1)}" if year_match else ""
            return f"[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร{year_str}]"
        elif "fee" in fname or "ค่าเทอม" in fname:
            return "[หมวดหมู่: ค่าเทอมและการเงิน]"
        elif "course" in fname or "วิชา" in fname:
            return "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]"
        elif "degree" in fname or "แผน" in fname or "curriculum" in fname:
            return "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร]"
        elif "teacher" in fname or "อาจารย์" in fname or "อจ" in fname:
            return "[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]"
        elif "co-op" in fname or "สหกิจ" in fname or "การฝึกงาน" in fname or "internship" in fname:
            return "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]"
        elif "company" in fname or "บริษัท" in fname or "mou" in fname:
            return "[หมวดหมู่: เครือข่ายบริษัท/MOU]"
        elif "สาขา" in fname or "department" in fname:
            return "[หมวดหมู่: ข้อมูลสาขาวิชา]"
        return "[หมวดหมู่: ข้อมูลทั่วไป]"

    def _romanize_filename(self, thai_name):
        mapping = {
            "ค่าเทอม": "fees",
            "รายชื่ออาจารย์": "teachers",
            "บริษัท": "companies",
            "บริษัทMOU": "com_mou",
            "สหกิจ": "co-op",
            "การฝึกงาน": "internship",
            "สาขา": "department",
            "วิชา": "course",
            "อจ": "teacher",
            "อาจารย์": "teacher",
            "mockup": "mockup",
            "ค่า": "fees",
            "เทอม": "term",
            "รายชื่อ": "list",
            "เพื่อการศึกษา": "education",
        }
        for thai, ascii_name in mapping.items():
            thai_name = thai_name.replace(thai, ascii_name)
        thai_name = re.sub(r'[\u0E00-\u0E7F]', '', thai_name)
        thai_name = re.sub(r'[_\s]+', '_', thai_name).strip('_')
        return thai_name

    def auto_detect_chunk_method(self, filename):
        filename_lower = filename.lower()
        # degree plan ต้องตรวจก่อน เพราะชื่ออาจมีคำว่า "วิชา" หรือ "แผน" ปน
        if "degreeplan" in filename_lower or "degree_plan" in filename_lower:
            return self.chunk_by_section, "chunk_by_section", "Section Chunking (#### level — best for Degree Plans)"
        elif "mockup" in filename_lower and ("อจ" in filename or "teacher" in filename_lower):
            return self.chunk_markdown_hierarchy, "markdown_hierarchy", "Markdown Hierarchy (Structure-aware - best for Teachers)"
        elif "ค่าเทอม" in filename or "fees" in filename_lower:
            return self.chunk_markdown_tables, "markdown_tables", "Markdown Tables (Table-aware - best for Fees)"
        elif "วิชา" in filename or "course" in filename_lower:
            return self.chunk_markdown_tables, "markdown_tables", "Markdown Tables (best for Course Lists)"
        elif "degree" in filename_lower or "curriculum" in filename_lower or "แผนการเรียน" in filename:
            return self.chunk_markdown_semantic, "markdown_semantic", "Markdown Semantic (Best for Curriculum planning)"
        elif "บริษัท" in filename or "mou" in filename_lower or "companies" in filename_lower:
            return self.chunk_paragraphs, "paragraphs", "Paragraphs (Best for Companies lists)"
        elif "สาขา" in filename or "department" in filename_lower:
            return self.chunk_paragraphs, "paragraphs", "Paragraphs (Best for Department overview)"
        elif "รายชื่ออาจารย์" in filename or "อาจารย์" in filename or "teachers" in filename_lower:
            return self.chunk_markdown_hierarchy, "markdown_hierarchy", "Markdown Hierarchy (Structure-aware)"
        elif "สหกิจ" in filename or "co-op" in filename_lower or "การฝึกงาน" in filename or "internship" in filename_lower:
            return self.chunk_by_section, "chunk_by_section", "Section Chunking (#### level — best for Internship/Co-op with timeline)"
        else:
            return self.chunk_markdown_semantic, "markdown_semantic", "Markdown Semantic (Mixed content)"

    def auto_detect_chunk_method_with_type(self, filename, file_type):
        if file_type == "paragraph":
            return self.chunk_paragraphs, "paragraphs", "Paragraphs (Long-form content)"
        else:
            return self.auto_detect_chunk_method(filename)

    def embed_chunks(self, chunks, save_name, verbose=True, export_pkl=True):
        if verbose:
            print(f"กำลัง embedding {len(chunks)} chunks ...")

        embeddings = self.model.encode(chunks)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(np.array(embeddings).astype("float32"))

        ascii_name = self._romanize_filename(save_name)
        faiss_path = os.path.join(self.output_dir, f"{ascii_name}.faiss")
        faiss.write_index(index, faiss_path)

        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")
        with open(chunks_path, "w", encoding="utf-8") as f:
            for c in chunks:
                # [แก้ไข]: ใช้ตัวคั่นเฉพาะเพื่อไม่ให้ซ้ำกับ Markdown
                f.write(c + "\n===CHUNK_SEPARATOR===\n")

        if verbose:
            print(f"บันทึกแล้ว: {faiss_path}")
            print(f"บันทึก chunk text: {chunks_path}")
        
        if export_pkl:
            pkl_path = os.path.join(self.output_dir, f"{save_name}.pkl")
            with open(pkl_path, "wb") as f:
                pickle.dump(embeddings.astype("float32"), f)
            if verbose:
                print(f"บันทึก embeddings: {pkl_path}\n")
        else:
            if verbose:
                print()

        return index, chunks, embeddings

    def process_file(self, file_path, chunk_func, save_name, verbose=True, export_pkl=True):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_func(text)
        tag = self._get_context_tag(os.path.basename(file_path))
        
        # Inject Context & Source Tag
        formatted_chunks = [f"[SOURCE: {os.path.basename(file_path)}]\n{tag}\n{c}" for c in chunks]

        if verbose:
            print(f"\nสร้าง chunk ได้ทั้งหมด: {len(formatted_chunks)}")
            if formatted_chunks:
                print("ตัวอย่าง chunk แรก:\n")
                print(formatted_chunks[0][:300], "\n")

        self.embed_chunks(formatted_chunks, save_name, verbose=verbose, export_pkl=export_pkl)

        ascii_name = self._romanize_filename(save_name)
        faiss_path = os.path.join(self.output_dir, f"{ascii_name}.faiss")
        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")
        pkl_path = os.path.join(self.output_dir, f"{save_name}.pkl") if export_pkl else None
        
        return formatted_chunks, faiss_path, chunks_path, pkl_path
    
    def process_multiple_files(self, file_paths, chunk_funcs, save_name, verbose=True, export_pkl=True):
        all_chunks = []

        for file_path, chunk_func in zip(file_paths, chunk_funcs):
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"ไม่พบไฟล์ {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            chunks = chunk_func(text)
            
            # Fetch intelligent tag based on file name
            context_tag = self._get_context_tag(os.path.basename(file_path))

            if verbose:
                print(f"📄 {os.path.basename(file_path)} → {len(chunks)} chunks")

            # Inject both Source and Context Tag automatically
            for c in chunks:
                all_chunks.append(f"[SOURCE: {os.path.basename(file_path)}]\n{context_tag}\n{c}")

        if not all_chunks:
            raise ValueError("ไม่พบ chunk ใด ๆ จากไฟล์ที่เลือก")

        if verbose:
            print(f"\n✅ รวมทั้งหมด {len(all_chunks)} chunks จาก {len(file_paths)} ไฟล์")

        return self.embed_chunks(all_chunks, save_name, verbose=verbose, export_pkl=export_pkl)

    def load_index_and_chunks(self, save_name, copy_to_ascii=None):
        ascii_name = self._romanize_filename(save_name)
        idx_path = os.path.join(self.output_dir, f"{ascii_name}.faiss")
        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")

        if not os.path.exists(idx_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ดัชนี: {idx_path}")
        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ chunks: {chunks_path}")

        if copy_to_ascii:
            import shutil
            shutil.copyfile(idx_path, copy_to_ascii)
            idx_path = copy_to_ascii

        index = faiss.read_index(idx_path)
        with open(chunks_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        # [แก้ไข]: อ่านไฟล์แล้วแยกข้อมูลด้วยตัวคั่นเฉพาะ
        chunks = [c.strip() for c in raw.split("\n===CHUNK_SEPARATOR===\n") if c.strip()]
        return index, chunks

    def search(self, query, save_name, top_k=5, copy_to_ascii=None):
        try:
            index, chunks = self.load_index_and_chunks(save_name, copy_to_ascii=copy_to_ascii)
        except Exception as e:
            print(f"ไม่สามารถโหลด FAISS index: {e}")
            raise

        q_vec = self.model.encode([query]).astype("float32")
        D, I = index.search(q_vec, top_k)

        results = []
        for dist, idx in zip(D[0], I[0]):
            if 0 <= idx < len(chunks):
                results.append({
                    "distance": float(dist),
                    "chunk": chunks[idx]
                })

        return results


if __name__ == "__main__":
    import glob
    
    embedding_proc = EmbeddingProcessor()
    
    preprocess_output_dir = os.path.join(os.path.dirname(__file__), "..", "preprocess", "output")
    if not os.path.exists(preprocess_output_dir):
        print(f"Error: {preprocess_output_dir}/ folder not found")
        print("Please run preprocess_knowledge.py first to generate cleaned files")
        exit(1)
    
    structured_output_dir = os.path.join(preprocess_output_dir, "structured")
    paragraph_output_dir = os.path.join(preprocess_output_dir, "paragraph")
    
    structured_clean_files = sorted(glob.glob(os.path.join(structured_output_dir, "*_clean.txt"))) if os.path.exists(structured_output_dir) else []
    paragraph_clean_files = sorted(glob.glob(os.path.join(paragraph_output_dir, "*_clean.txt"))) if os.path.exists(paragraph_output_dir) else []
    
    all_clean_files = structured_clean_files + paragraph_clean_files
    file_types = ["structured"] * len(structured_clean_files) + ["paragraph"] * len(paragraph_clean_files)
    
    if not all_clean_files:
        print(f"\nNo cleaned files found in {structured_output_dir}/ or {paragraph_output_dir}/ folders")
        print("Please run preprocess_knowledge.py first")
        exit(1)
    
    while True:
        print(f"\nFound {len(all_clean_files)} cleaned file(s):")
        for i, (f, ftype) in enumerate(zip(all_clean_files, file_types), 1):
            basename = os.path.basename(f)
            print(f"  {i}. [{ftype}] {basename}")
        
        try:
            choices = input("\nSelect file numbers (comma-separated, e.g. 1,3,5): ")
            indices = [int(x.strip()) - 1 for x in choices.split(",")]

            for i in indices:
                if i < 0 or i >= len(all_clean_files):
                    raise ValueError

            selected_files = [all_clean_files[i] for i in indices]
            selected_types = [file_types[i] for i in indices]

        except ValueError:
            print(f"Please enter valid numbers between 1 and {len(all_clean_files)} (comma-separated)")
            continue
        
        chunk_funcs = []

        for f, ftype in zip(selected_files, selected_types):
            basename = os.path.basename(f)
            detected_func, detected_method, detected_desc = (
                embedding_proc.auto_detect_chunk_method_with_type(basename, ftype)
            )

            print(f"\n📄 File: {basename}")
            print(f"📁 File type: {ftype}")
            print(f"✓ Recommended method: {detected_desc}")
            print("Chunking method options:")
            print("1 = Paragraphs (Long-form content with overlap)")
            print("2 = Markdown Tables (Table-aware, keeps context)")
            print("3 = Markdown Hierarchy (Respects ### heading structure)")
            print("4 = Markdown Semantic (Mixed content: tables + text)")
            print("5 = Section Chunking (#### level — for Degree Plans)")
            print("0 = Use recommended method")

            chunk_choice = input("Select method (0–5): ")

            if chunk_choice == "0":
                chunk_func = detected_func
                method_name = detected_method
            elif chunk_choice == "1":
                chunk_func = embedding_proc.chunk_paragraphs
                method_name = "paragraphs"
            elif chunk_choice == "2":
                chunk_func = embedding_proc.chunk_markdown_tables
                method_name = "markdown_tables"
            elif chunk_choice == "3":
                chunk_func = embedding_proc.chunk_markdown_hierarchy
                method_name = "markdown_hierarchy"
            elif chunk_choice == "4":
                chunk_func = embedding_proc.chunk_markdown_semantic
                method_name = "markdown_semantic"
            elif chunk_choice == "5":
                chunk_func = embedding_proc.chunk_by_section
                method_name = "chunk_by_section"
            else:
                print("Invalid choice, use recommended method")
                chunk_func = detected_func
                method_name = detected_method

            print(f"→ Selected chunk method: {method_name}")
            chunk_funcs.append(chunk_func)

        save_name = "combined_embedded"
        
        try:
            print(f"\nProcessing files and merging into FAISS...")
            embedding_proc.process_multiple_files(
                selected_files,
                chunk_funcs,
                save_name,
                verbose=True,
                export_pkl=True
            )

        except Exception as e:
            print(f"Error: {e}")
        
        cont = input("\nContinue with other files? (y/n): ")
        print()
        if cont.lower() != "y":
            break