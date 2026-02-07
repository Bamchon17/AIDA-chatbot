import re
import os
import glob


class TextProcessor:
    """Class to handle text processing: abbreviations, company terms, and number-to-Thai conversion"""

    # Abbreviation mappings
    ABBREVIATIONS = {
        # Thai abbreviations
        "รศ.ดร.": "รองศาสตราจารย์ดอกเตอร์",
        "ผศ.ดร.": "ผู้ช่วยศาสตราจารย์ดอกเตอร์",
        "ศ.ดร.": "ศาสตราจารย์ดอกเตอร์",
        "ดร.": "ดอกเตอร์",
        "อ.": "อาจารย์",
        "พ.ศ.": "พุทธศักราช",
        "กยศ.": "กองทุนเงินให้กู้ยืมเพื่อการศึกษา",
        "บ.ก.": "บริษัทจำกัด",
        # English academic abbreviations
        "Ph.D.": "Doctor of Philosophy",
        "PhD.": "Doctor of Philosophy",
        "Ph.D": "Doctor of Philosophy",
        "PhD": "Doctor of Philosophy",
        "M.Eng.": "Master of Engineering",
        "M.Eng": "Master of Engineering",
        "M.Sc.": "Master of Science",
        "M.Sc": "Master of Science",
        "M.B.A.": "Master of Business Administration",
        "MBA.": "Master of Business Administration",
        "MBA": "Master of Business Administration",
        "B.Eng.": "Bachelor of Engineering",
        "B.Eng": "Bachelor of Engineering",
        "B.Sc.": "Bachelor of Science",
        "B.Sc": "Bachelor of Science",
        "B.A.": "Bachelor of Arts",
        "B.A": "Bachelor of Arts",
        "M.A.": "Master of Arts",
        "M.A": "Master of Arts",
    }

    # Company name patterns
    COMPANY_PATTERNS = [
        r"Co\.,\s*Ltd\.",
        r"CO\.,\s*LTD\.",
        r"Co\.,\s*LTD\.",
        r"Co\.,\s*Ltd",
    ]

    # Thai number and unit names
    THAI_NUM = ["ศูนย์","หนึ่ง","สอง","สาม","สี่","ห้า","หก","เจ็ด","แปด","เก้า"]
    THAI_UNIT = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"]

    def __init__(self, input_dir=None, output_dir=None):
        """Initialize processor with input and output directories
        
        Args:
            input_dir: Input directory path (default: ./input in same folder as this file)
            output_dir: Output directory path (default: ./output in same folder as this file)
        """
        # Use relative paths from the location of this file
        if input_dir is None:
            input_dir = os.path.join(os.path.dirname(__file__), "input")
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            
        self.input_dir = input_dir
        self.output_dir = output_dir
        
        # Subdirectories for hybrid strategy
        self.structured_input_dir = os.path.join(self.input_dir, "structured")
        self.paragraph_input_dir = os.path.join(self.input_dir, "paragraph")
        
        # Output subdirectories (to maintain file type info)
        self.structured_output_dir = os.path.join(self.output_dir, "structured")
        self.paragraph_output_dir = os.path.join(self.output_dir, "paragraph")
        
        self._ensure_directories()

    def _ensure_directories(self):
        """Verify that directories exist (create only if missing)"""
        dirs_to_create = [
            self.input_dir,
            self.output_dir,
            self.structured_input_dir,
            self.paragraph_input_dir,
            self.structured_output_dir,
            self.paragraph_output_dir
        ]
        for d in dirs_to_create:
            if not os.path.exists(d):
                os.makedirs(d)

    def replace_abbreviations(self, text):
        """Replace Thai abbreviations with full forms"""
        for short, full in self.ABBREVIATIONS.items():
            text = text.replace(short, full)
        return text

    def replace_company_terms(self, text):
        """Replace company name patterns (Co., Ltd. → Company Limited)"""
        for pattern in self.COMPANY_PATTERNS:
            text = re.sub(pattern, "Company Limited", text, flags=re.IGNORECASE)
        return text

    def number_to_thai(self, n):
        """Convert a number to Thai word representation"""
        n = int(n)
        if n == 0:
            return "ศูนย์"

        result = ""
        unit_pos = 0

        while n > 0:
            digit = n % 10

            if digit != 0:
                if unit_pos == 1 and digit == 1:
                    result = "สิบ" + result
                elif unit_pos == 1 and digit == 2:
                    result = "ยี่สิบ" + result
                elif unit_pos == 0 and digit == 1 and n > 10:
                    result = "เอ็ด" + result
                else:
                    result = self.THAI_NUM[digit] + self.THAI_UNIT[unit_pos] + result

            unit_pos += 1

            if unit_pos == 6:
                result = "ล้าน" + result
                unit_pos = 0

            n //= 10

        return result

    def replace_numbers(self, text):
        """Replace formatted numbers with Thai word representation"""
        def convert(match):
            num = match.group().replace(",", "")
            return self.number_to_thai(num)

        return re.sub(r"\d{1,3}(?:,\d{3})+", convert, text)

    def chunk_paragraphs(self, text, chunk_size=500, overlap=100):
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


    def process_text(self, text, convert_numbers=True):
        """Apply all transformations to text
        
        Args:
            text: Input text to process
            convert_numbers: Whether to convert numbers to Thai words (default: True)
                            Set to False for structured data (tables, fees, etc.)
        """
        text = self.replace_abbreviations(text)
        text = self.replace_company_terms(text)
        if convert_numbers:
            text = self.replace_numbers(text)
        return text

    def process_file(self, input_path, output_path=None, verbose=True, convert_numbers=True):
        """Process a single file
        
        Args:
            input_path: Path to input file
            output_path: Path to output file (optional)
            verbose: Whether to print progress
            convert_numbers: Whether to convert numbers to Thai words
                            Set to False for structured data (tables, etc.)
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"ไม่พบไฟล์: {input_path}")

        # Read input
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Transform - pass convert_numbers parameter
        text = self.process_text(text, convert_numbers=convert_numbers)

        # Determine output path and directory based on input source
        if output_path is None:
            basename = os.path.basename(input_path)
            # Detect if file is from structured or paragraph directory
            if self.structured_input_dir in input_path:
                output_dir = self.structured_output_dir
            elif self.paragraph_input_dir in input_path:
                output_dir = self.paragraph_output_dir
            else:
                output_dir = self.output_dir
            
            output_path = os.path.join(output_dir, f"{os.path.splitext(basename)[0]}_clean.txt")

        # Write output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        if verbose:
            print(f"แปลงเสร็จแล้ว: {output_path}")
            print("---- ข้อความที่แปลงแล้ว ----")
            print(text)

        return output_path

    def list_input_files(self):
        """List all .txt files in input directory"""
        files = glob.glob(os.path.join(self.input_dir, "*.txt"))
        return sorted(files)

    def list_structured_files(self):
        """List all .txt files in structured input directory"""
        files = glob.glob(os.path.join(self.structured_input_dir, "*.txt"))
        return sorted(files)

    def list_paragraph_files(self):
        """List all .txt files in paragraph input directory"""
        files = glob.glob(os.path.join(self.paragraph_input_dir, "*.txt"))
        return sorted(files)

    def list_all_files_hybrid(self):
        """List all files from both structured and paragraph directories"""
        structured = self.list_structured_files()
        paragraph = self.list_paragraph_files()
        return {
            "structured": structured,
            "paragraph": paragraph,
            "total": len(structured) + len(paragraph)
        }

    def select_file(self):
        """Show list of files and let user select one"""
        files = self.list_input_files()

        if not files:
            print(f"ไม่พบไฟล์ .txt ในโฟลเดอร์ {self.input_dir}")
            return None

        print(f"\nไฟล์ที่พบ ({len(files)} ไฟล์):")
        for i, f in enumerate(files, 1):
            print(f"  {i}. {os.path.basename(f)}")

        while True:
            try:
                choice = int(input("เลือกไฟล์ (ตัวเลข): "))
                if 1 <= choice <= len(files):
                    return files[choice - 1]
                else:
                    print(f"กรุณาเลือกตัวเลขระหว่าง 1 ถึง {len(files)}")
            except ValueError:
                print("กรุณากรอกตัวเลข")

    def select_file_hybrid(self):
        """Show list of files from both structured and paragraph directories"""
        structured = self.list_structured_files()
        paragraph = self.list_paragraph_files()
        
        all_files = []
        file_types = []
        
        for f in structured:
            all_files.append(f)
            file_types.append("structured")
        
        for f in paragraph:
            all_files.append(f)
            file_types.append("paragraph")
        
        if not all_files:
            print(f"ไม่พบไฟล์ .txt ในโฟลเดอร์ structured และ paragraph")
            return None, None
        
        print(f"\nไฟล์ที่พบ ({len(all_files)} ไฟล์):")
        for i, (f, ftype) in enumerate(zip(all_files, file_types), 1):
            print(f"  {i}. [{ftype}] {os.path.basename(f)}")
        
        while True:
            try:
                choice = int(input("เลือกไฟล์ (ตัวเลข): "))
                if 1 <= choice <= len(all_files):
                    return all_files[choice - 1], file_types[choice - 1]
                else:
                    print(f"กรุณาเลือกตัวเลขระหว่าง 1 ถึง {len(all_files)}")
            except ValueError:
                print("กรุณากรอกตัวเลข")

    def process_all_files(self):
        """Process all files in input/structured and input/paragraph directories"""
        structured = self.list_structured_files()
        paragraph = self.list_paragraph_files()
        
        all_files = structured + paragraph
        file_types = ["structured"] * len(structured) + ["paragraph"] * len(paragraph)
        
        if not all_files:
            print(f"ไม่พบไฟล์ .txt ในโฟลเดอร์ structured และ paragraph")
            return

        print(f"พบ {len(all_files)} ไฟล์\n")
        for input_file, ftype in zip(all_files, file_types):
            try:
                # Structured files: don't convert numbers (preserve for RAG/embeddings)
                # Paragraph files: convert numbers to Thai (for TTS later)
                convert_numbers = (ftype == "paragraph")
                
                self.process_file(input_file, verbose=False, convert_numbers=convert_numbers)
                output_file = os.path.join(self.output_dir, f"{os.path.splitext(os.path.basename(input_file))[0]}_clean.txt")
                print(f"บันทึกไฟล์: {output_file}")
            except Exception as e:
                print(f"เกิดข้อผิดพลาดกับ {input_file}: {e}")


if __name__ == "__main__":
    processor = TextProcessor()

    while True:
        print("\n--- เมนูเลือกโหมด ---")
        print("1 = เลือกไฟล์ทีละไฟล์ (interactive mode)")
        print("2 = ประมวลผลทั้งหมด (all files at once)")
        print("0 = ออก")
        
        mode = input("\nเลือกโหมด (0/1/2): ")
        
        if mode == "0":
            print("ยกเลิก")
            break
        elif mode == "1":
            # Interactive mode - select file by file
            while True:
                input_file, file_type = processor.select_file_hybrid()

                if input_file is None:
                    print("ยกเลิก")
                    break

                # Ask about number conversion
                print(f"\n📋 ไฟล์ที่เลือก: {os.path.basename(input_file)}")
                print(f"📁 ประเภท: {file_type}")
                
                if file_type == "structured":
                    print("\n⚠️  ไฟล์ structured - โดยปกติไม่ควรแปลงตัวเลข")
                    print("ตัวเลขจะใช้สำหรับ RAG และ embeddings")
                    convert_opt = input("แปลงตัวเลขเป็นคำไทยหรือไม่? (y/n) [default: n]: ").lower()
                    convert_numbers = convert_opt == "y"
                else:
                    print("\n⚠️  ไฟล์ paragraph - ปกติแปลงตัวเลขเป็นคำไทย")
                    convert_opt = input("แปลงตัวเลขเป็นคำไทยหรือไม่? (y/n) [default: y]: ").lower()
                    convert_numbers = convert_opt != "n"

                try:
                    print(f"\nประมวลผล [{file_type}]: {os.path.basename(input_file)}")
                    processor.process_file(input_file, verbose=True, convert_numbers=convert_numbers)
                    print()
                except Exception as e:
                    print(f"เกิดข้อผิดพลาด: {e}\n")

                cont = input("ทำต่อไหม (y/n): ")
                if cont.lower() != "y":
                    break
        elif mode == "2":
            # Process all files at once
            try:
                processor.process_all_files()
            except Exception as e:
                print(f"เกิดข้อผิดพลาด: {e}")
            break
        else:
            print("ตัวเลือกไม่ถูกต้อง")
