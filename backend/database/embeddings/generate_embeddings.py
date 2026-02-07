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

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model_name=None, output_dir=None):
        """
        Initialize with embedding model and output directory.
        
        Args:
            model_name: Name of the sentence transformer model
            output_dir: Directory to save embeddings and chunks (default: output_embeddings in same folder)
        """
        if model_name is None:
            model_name = self.MODEL_NAME
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "output_embeddings")
            
        self.model = SentenceTransformer(model_name)
        self.output_dir = output_dir
        
        # Verify output directory exists (create only if missing)
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    # =====================
    # CHUNK FUNCTIONS
    # =====================

    @staticmethod
    def chunk_teachers(text):
        """Chunk text for teacher list (by numbered items)"""
        chunks = []
        parts = re.split(r"\n\s*\d+\.\s*", text)
        for part in parts:
            part = part.strip()
            if len(part) > 20:
                chunks.append(part)
        return chunks

    @staticmethod
    def chunk_fees(text):
        """Chunk text for fee list (by year/term)"""
        chunks = []
        lines = text.split("\n")
        buffer = ""
        for line in lines:
            line = line.strip()
            if line.startswith("ปี"):
                if buffer:
                    chunks.append(buffer.strip())
                buffer = line
            else:
                buffer += " " + line
        if buffer:
            chunks.append(buffer.strip())
        return [c for c in chunks if len(c) > 20]

    @staticmethod
    def chunk_companies(text):
        """Chunk text for company list (by numbered items)"""
        chunks = []
        parts = re.split(r"\n\s*\d+\.\s*", text)
        for part in parts:
            part = part.strip()
            if len(part) > 20:
                chunks.append(part)
        return chunks

    @staticmethod
    def chunk_mockup_teachers(text):
        """Chunk text for mockup teacher data (by teacher name/header)"""
        chunks = []
        lines = text.split("\n")
        buffer = ""
        
        for line in lines:
            # Check if line is a teacher name header (### or ###)
            if line.strip().startswith("###"):
                if buffer.strip() and len(buffer.strip()) > 20:
                    chunks.append(buffer.strip())
                buffer = line
            else:
                buffer += "\n" + line
        
        # Add the last chunk
        if buffer.strip() and len(buffer.strip()) > 20:
            chunks.append(buffer.strip())
        
        return chunks

    @staticmethod
    def chunk_paragraphs(text, chunk_size=500, overlap=100):
        """
        Chunk text by paragraphs with overlapping for long-form content.
        This is used for detailed descriptions, course information, etc.
        
        Args:
            text: Input text to chunk
            chunk_size: Target size of each chunk in characters (approximate)
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        # Split by paragraphs (double newlines)
        paragraphs = re.split(r'\n\s*\n', text.strip())
        
        chunks = []
        buffer = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If adding this paragraph exceeds chunk_size, save buffer and start new
            if buffer and len(buffer) + len(paragraph) > chunk_size:
                chunks.append(buffer.strip())
                # Add overlap from the last paragraph
                buffer = paragraph
            else:
                if buffer:
                    buffer += "\n\n" + paragraph
                else:
                    buffer = paragraph
        
        # Add remaining content
        if buffer:
            chunks.append(buffer.strip())
        
        # Ensure minimum chunk size
        return [c for c in chunks if len(c) > 50]

    @staticmethod
    def chunk_markdown_tables(text):
        """
        Chunk markdown with tables - keeps tables with surrounding context.
        Splits by major headings and preserves table structure.
        
        Best for: Data tables with headers (fees, schedules, etc.)
        
        Args:
            text: Input markdown text with tables
            
        Returns:
            List of text chunks (each with complete table + context)
        """
        chunks = []
        
        # Split by level 2 headings (##)
        sections = re.split(r'^## ', text, flags=re.MULTILINE)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # Further split by level 3 headings (###) if no tables
            if '|' not in section:  # No tables in this section
                subsections = re.split(r'^### ', section, flags=re.MULTILINE)
                for subsection in subsections:
                    subsection = subsection.strip()
                    if len(subsection) > 30:
                        chunks.append(subsection)
            else:
                # Keep section with table intact
                if len(section) > 30:
                    chunks.append(section)
        
        return chunks

    @staticmethod
    def chunk_markdown_hierarchy(text):
        """
        Chunk by markdown hierarchy - respects document structure.
        Each chunk is a complete section from heading to next heading.
        
        Best for: Structured documents with heading hierarchy (faculty list, etc.)
        
        Args:
            text: Input markdown text
            
        Returns:
            List of text chunks (complete sections)
        """
        chunks = []
        
        # Split by level 3 headings (###) first (smallest meaningful unit)
        parts = re.split(r'^### ', text, flags=re.MULTILINE)
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # Add the heading back if it's not the first part
            if i > 0:
                # Extract the first line as heading
                lines = part.split('\n')
                part = '### ' + part
            
            if len(part) > 30:
                chunks.append(part)
        
        return chunks

    @staticmethod
    def chunk_markdown_semantic(text, chunk_size=400):
        """
        Chunk markdown semantically - keeps related information together.
        Handles tables + text intelligently with optimal chunk sizes.
        
        Best for: Mixed content (tables + descriptions)
        
        Args:
            text: Input markdown text
            chunk_size: Target characters per chunk (default: 400)
            
        Returns:
            List of text chunks (well-balanced semantic units)
        """
        chunks = []
        
        # Split by headings (### level 3)
        heading_pattern = r'^### '
        sections = re.split(heading_pattern, text, flags=re.MULTILINE)
        
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue
            
            # Add heading back
            if i > 0:
                section = '### ' + section
            
            # Check if section contains a table
            if '|' in section:
                # For sections with tables, keep them together with context
                # Split by double newline but keep tables intact
                parts = section.split('\n\n')
                current_chunk = ""
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # If adding this part would exceed chunk_size and we have content
                    if current_chunk and len(current_chunk) + len(part) > chunk_size:
                        chunks.append(current_chunk.strip())
                        current_chunk = part
                    else:
                        if current_chunk:
                            current_chunk += "\n\n" + part
                        else:
                            current_chunk = part
                
                # Add remaining content
                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                # For text-only sections, split by paragraphs
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
        
        # Filter out very small chunks
        return [c for c in chunks if len(c) > 30]



    # =====================
    # EMBEDDING FUNCTIONS
    # =====================

    def _romanize_filename(self, thai_name):
        """Convert Thai filename to ASCII romanized version for Windows compatibility"""
        # Simple mapping of common Thai words to ASCII
        mapping = {
            "ค่าเทอม": "fees",
            "รายชื่ออาจารย์": "teachers",
            "บริษัท": "companies",
            "บริษัทMOU": "com_mou",
            "สหกิจ": "co-op",
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
        
        # Remove any remaining Thai characters using regex
        # Thai Unicode range: U+0E00 to U+0E7F
        thai_name = re.sub(r'[\u0E00-\u0E7F]', '', thai_name)
        
        # Clean up any double underscores or spaces
        thai_name = re.sub(r'[_\s]+', '_', thai_name).strip('_')
        
        return thai_name

    def auto_detect_chunk_method(self, filename):
        """
        Auto-detect chunking method based on filename patterns.
        
        Args:
            filename: The filename to analyze
            
        Returns:
            Tuple of (chunk_function, method_name, confidence_description)
        """
        filename_lower = filename.lower()
        
        # Pattern matching for different file types
        if "mockup" in filename_lower and ("อจ" in filename or "teacher" in filename_lower):
            return self.chunk_markdown_hierarchy, "markdown_hierarchy", "Markdown Hierarchy (structure-aware)"
        elif "ค่าเทอม" in filename or "fees" in filename_lower:
            return self.chunk_markdown_tables, "markdown_tables", "Markdown Tables (table-aware)"
        elif "degree" in filename_lower or "curriculum" in filename_lower or "แผนการเรียน" in filename:
            return self.chunk_markdown_semantic, "markdown_semantic", "Markdown Semantic (curriculum planning)"
        elif "บริษัท" in filename or "mou" in filename_lower or "companies" in filename_lower:
            return self.chunk_companies, "companies", "Companies (by numbered items)"
        elif "รายชื่ออาจารย์" in filename or "teachers" in filename_lower:
            return self.chunk_markdown_hierarchy, "markdown_hierarchy", "Markdown Hierarchy (structure-aware)"
        else:
            # Default based on file content hints
            return self.chunk_markdown_semantic, "markdown_semantic", "Markdown Semantic (mixed content)"

    def auto_detect_chunk_method_with_type(self, filename, file_type):
        """
        Auto-detect chunking method based on filename and file type (structured or paragraph).
        
        Args:
            filename: The filename to analyze
            file_type: Type of file - "structured" or "paragraph"
            
        Returns:
            Tuple of (chunk_function, method_name, confidence_description)
        """
        if file_type == "paragraph":
            return self.chunk_paragraphs, "paragraphs", "Paragraphs (long-form content)"
        else:
            # Use original detection for structured files
            return self.auto_detect_chunk_method(filename)

    def embed_chunks(self, chunks, save_name, verbose=True, export_pkl=True):
        """
        Embed chunks and save FAISS index + chunk text to output directory.
        
        Args:
            chunks: List of text chunks
            save_name: Base name for output files (without extension, e.g., "companiesMOU_embedded")
            verbose: Whether to print progress
            export_pkl: Whether to export embeddings as .pkl file
            
        Returns:
            Tuple of (index, chunks, embeddings_array)
        """
        if verbose:
            print(f"กำลัง embedding {len(chunks)} chunks ...")

        embeddings = self.model.encode(chunks)

        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(np.array(embeddings).astype("float32"))

        # Use ASCII-safe filename for FAISS (Windows compatibility with Thai filenames)
        ascii_name = self._romanize_filename(save_name)
        
        # Save FAISS index to output directory with ASCII filename
        faiss_path = os.path.join(self.output_dir, f"{ascii_name}.faiss")
        faiss.write_index(index, faiss_path)

        # Save chunk text with original name
        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")
        with open(chunks_path, "w", encoding="utf-8") as f:
            for c in chunks:
                # Keep newlines for readability in RAG chunks
                f.write(c + "\n---\n")

        if verbose:
            print(f"บันทึกแล้ว: {faiss_path}")
            print(f"บันทึก chunk text: {chunks_path}")
        
        # Export embeddings as pickle file with original name
        if export_pkl:
            pkl_path = os.path.join(self.output_dir, f"{save_name}.pkl")
            with open(pkl_path, "wb") as f:
                pickle.dump(embeddings.astype("float32"), f)
            if verbose:
                print(f"บันทึก embeddings: {pkl_path}\n")
        else:
            pkl_path = None
            if verbose:
                print()

        return index, chunks, embeddings

    def process_file(self, file_path, chunk_func, save_name, verbose=True, export_pkl=True):
        """
        Process a single file: read, chunk, embed, and save to output directory.
        
        Args:
            file_path: Path to input text file
            chunk_func: Function to use for chunking (chunk_teachers, chunk_fees, etc.)
            save_name: Base name for output files (e.g., "companiesMOU_embedded")
            verbose: Whether to print progress
            export_pkl: Whether to export embeddings as .pkl file
            
        Returns:
            Tuple of (chunks, faiss_path, chunks_path, pkl_path)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ {file_path}")

        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Chunk
        chunks = chunk_func(text)

        if verbose:
            print(f"\nสร้าง chunk ได้ทั้งหมด: {len(chunks)}")
            if chunks:
                print("ตัวอย่าง chunk แรก:\n")
                print(chunks[0][:300], "\n")

        # Embed and save
        self.embed_chunks(chunks, save_name, verbose=verbose, export_pkl=export_pkl)

        ascii_name = self._romanize_filename(save_name)
        faiss_path = os.path.join(self.output_dir, f"{ascii_name}.faiss")
        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")
        pkl_path = os.path.join(self.output_dir, f"{save_name}.pkl") if export_pkl else None
        
        return chunks, faiss_path, chunks_path, pkl_path

    def load_index_and_chunks(self, save_name, copy_to_ascii=None):
        """
        Load FAISS index and chunks from output directory.
        Automatically handles Thai filenames by converting to ASCII for FAISS.
        
        Args:
            save_name: Base name of saved files (e.g., "companiesMOU_embedded")
            copy_to_ascii: If provided, copy .faiss to ASCII filename first (workaround for Windows Thai names)
            
        Returns:
            Tuple of (index, chunks)
        """
        # Use ASCII-safe filename for FAISS lookup
        ascii_name = self._romanize_filename(save_name)
        
        idx_path = os.path.join(self.output_dir, f"{ascii_name}.faiss")
        chunks_path = os.path.join(self.output_dir, f"{save_name}_chunk.txt")

        if not os.path.exists(idx_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ดัชนี: {idx_path}")
        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ chunks: {chunks_path}")

        # Copy to ASCII name if needed (Windows Thai filename issue)
        if copy_to_ascii:
            import shutil
            shutil.copyfile(idx_path, copy_to_ascii)
            idx_path = copy_to_ascii

        index = faiss.read_index(idx_path)

        with open(chunks_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        chunks = [c.strip() for c in raw.split("\n---\n") if c.strip()]

        return index, chunks

    def search(self, query, save_name, top_k=5, copy_to_ascii=None):
        """
        Search for similar chunks using query text.
        
        Args:
            query: Query text
            save_name: Base name of saved embedding files
            top_k: Number of top results to return
            copy_to_ascii: ASCII filename to copy .faiss to (workaround)
            
        Returns:
            List of dicts with 'distance' and 'chunk' keys
        """
        try:
            index, chunks = self.load_index_and_chunks(save_name, copy_to_ascii=copy_to_ascii)
        except Exception as e:
            print(f"ไม่สามารถโหลด FAISS index: {e}")
            raise

        # Encode query
        q_vec = self.model.encode([query]).astype("float32")

        # Search
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
    # Interactive mode for processing files from preprocess output/ folder (hybrid strategy)
    import glob
    
    # Initialize embedding processor
    embedding_proc = EmbeddingProcessor()
    
    # Check if output folder exists
    preprocess_output_dir = os.path.join(os.path.dirname(__file__), "..", "preprocess", "output")
    if not os.path.exists(preprocess_output_dir):
        print(f"Error: {preprocess_output_dir}/ folder not found")
        print("Please run preprocess_knowledge.py first to generate cleaned files")
        exit(1)
    
    # Get files from structured and paragraph subdirectories
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
        
        # Get file choice
        try:
            choice = int(input("\nSelect file (number): "))
            if choice < 1 or choice > len(all_clean_files):
                print(f"Please enter number between 1 and {len(all_clean_files)}")
                continue
            selected_file = all_clean_files[choice - 1]
            file_type = file_types[choice - 1]
        except ValueError:
            print("Please enter a valid number")
            continue
        
        # Determine chunking method based on filename and file type
        basename = os.path.basename(selected_file)
        
        # Auto-detect chunking method
        detected_func, detected_method, detected_desc = embedding_proc.auto_detect_chunk_method_with_type(basename, file_type)
        
        print(f"\n📋 Detected file: {basename}")
        print(f"📁 File type: {file_type}")
        print(f"✓ Recommended method: {detected_desc}")
        print("\nChunking method options:")
        print("1 = Paragraphs (long-form content with overlap)")
        print("2 = Markdown Tables (table-aware, keeps tables with context)")
        print("3 = Markdown Hierarchy (respects heading structure)")
        print("4 = Markdown Semantic (mixed content: tables + text)")
        print("0 = Use recommended method (above)")
        
        chunk_choice = input("\nSelect method (0, 1-4): ")
        
        if chunk_choice == "0":
            # Use auto-detected method
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
        else:
            print("Invalid choice")
            continue
        
        # Generate output name from input filename (remove _clean suffix and romanize)
        clean_basename = basename.replace("_clean.txt", "")
        romanized_basename = embedding_proc._romanize_filename(clean_basename)
        save_name = romanized_basename + "_embedded"
        
        try:
            print(f"\nProcessing: {basename}")
            print(f"Chunking method: {method_name}")
            embedding_proc.process_file(selected_file, chunk_func, save_name, verbose=True, export_pkl=True)
        except Exception as e:
            print(f"Error: {e}")
        
        cont = input("Continue? (y/n): ")
        print()
        if cont.lower() != "y":
            break
