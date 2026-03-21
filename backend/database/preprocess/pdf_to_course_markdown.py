import pdfplumber
import re


# -----------------------------
# Extract text from PDF
# -----------------------------
def extract_text(pdf_path):

    text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:

            t = page.extract_text()

            if t:
                text += t + "\n"

    return text


# -----------------------------
# Clean text
# -----------------------------
def clean_text(text):

    text = text.replace("–", "-")

    text = re.sub(r'\r', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', '\n', text)

    # remove header/footer
    text = re.sub(r'หลักสูตรปริญญาตรี.+?\d+', '', text)

    return text


# -----------------------------
# Detect category and group
# -----------------------------
def detect_category_group(text):

    lines = text.split("\n")

    current_category = "ไม่ระบุ"
    current_group = "ไม่ระบุ"

    mapping = {}

    for line in lines:

        line = line.strip()

        # หมวด
        cat_match = re.search(r'หมวดวิชา(.+)', line)
        if cat_match:
            current_category = "วิชา" + cat_match.group(1).strip()

        # กลุ่ม
        group_match = re.search(r'กลุ่มวิชา(.+)', line)
        if group_match:
            current_group = "วิชา" + group_match.group(1).strip()

        # รหัสวิชา
        code_match = re.search(r'\b([A-Z]{2,4}\d{3})\b', line)

        if code_match:

            code = code_match.group(1)

            mapping[code] = (current_category, current_group)

    return mapping


# -----------------------------
# Split courses
# -----------------------------
def split_courses(text):

    pattern = r'\n([A-Z]{2,4}\d{3})\s'

    parts = re.split(pattern, "\n" + text)

    courses = []

    for i in range(1, len(parts), 2):

        code = parts[i]
        content = parts[i+1]

        courses.append((code, content))

    return courses


# -----------------------------
# Parse course
# -----------------------------
def parse_course(code, content):

    lines = content.split("\n")

    course_name = ""
    credit = "ไม่ระบุ"

    thai_lines = []
    eng_lines = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # credit
        credit_match = re.search(
            r'(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)',
            line
        )

        if credit_match:

            total = credit_match.group(1)
            lec = credit_match.group(2)
            lab = credit_match.group(3)
            selfstudy = credit_match.group(4)

            credit = f"{total} ({lec}-{lab}-{selfstudy})"
            continue

        # course name
        if course_name == "" and re.search(r'[A-Za-z]', line):

            course_name = re.sub(
                r'\d+\s*\(\d+-\d+-\d+\)',
                '',
                line
            ).strip()

            continue

        # thai
        if re.search(r'[\u0E00-\u0E7F]', line):

            thai_lines.append(line)
            continue

        # english
        if re.search(r'[A-Za-z]', line):

            eng_lines.append(line)

    thai_desc = " ".join(thai_lines)
    eng_desc = " ".join(eng_lines)

    return course_name, credit, thai_desc, eng_desc


# -----------------------------
# Build markdown
# -----------------------------
def build_markdown(courses, mapping):

    chunks = []

    for code, content in courses:

        name, credit, thai, eng = parse_course(code, content)

        category, group = mapping.get(code, ("ไม่ระบุ", "ไม่ระบุ"))

        chunk = f"""
## {code} - {name}
หน่วยกิต: {credit}  
หมวด: {category}  
กลุ่ม: {group}

### คำอธิบายรายวิชา (ภาษาไทย)
{thai}

### Course Description (English)
{eng}"""

        chunks.append(chunk)

    return "\n".join(chunks)


# -----------------------------
# Main
# -----------------------------
def convert_pdf_to_markdown(pdf_path, output_path):

    print("Extracting PDF text...")
    text = extract_text(pdf_path)

    print("Cleaning text...")
    text = clean_text(text)

    print("Detecting category and group...")
    mapping = detect_category_group(text)

    print("Splitting courses...")
    courses = split_courses(text)

    print("Courses found:", len(courses))

    print("Building markdown...")
    markdown = build_markdown(courses, mapping)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print("Done!")


# -----------------------------
# RUN
# -----------------------------
pdf_file = r"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\input\paragraph\คำอธิบายรายวิชา_2568.pdf"

output_file = r"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\output\paragraph\รายวิชา_2568_clean1.txt"

convert_pdf_to_markdown(pdf_file, output_file)