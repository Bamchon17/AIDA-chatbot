"""
แปลงตารางแผนการเรียน AI Engineering (PDF) → Markdown แบบ structured
รองรับ: ปีการศึกษา 2565, 2566, 2567, 2568
เหมาะสำหรับ RAG embedding
"""

import pdfplumber, os, sys

# =========================================================
# PAGE CONFIG  (page_num 1-based, table_index 0-based)
# tuple: (page_num, year, semester_key, table_index)
# =========================================================
YEAR_CONFIG = {
    "2565": {
        "path": r"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\input\structured\Degreeplan-AI 2565.pdf",
        "contexts": [
            (10, 1, "First Semester 1/1", 0),
            (10, 1, "First Semester 1/2", 1),
            (11, 1, "Second Semester",    0),
            (11, 1, "Summer Session",     1),
            (12, 2, "First Semester",     0),
            (13, 2, "Second Semester",    0),
            (13, 2, "Summer Session",     1),
            (14, 3, "First Semester",     0),
            (14, 3, "Second Semester",    1),
            (15, 3, "Summer Session",     0),
            (16, 4, "First Semester",     0),
            (16, 4, "Second Semester",    2),
        ],
    },
    "2566": {
        "path": r"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\input\structured\Degreeplan-AI 2566.pdf",
        "contexts": [
            (11, 1, "First Semester 1/1", 0),
            (11, 1, "First Semester 1/2", 1),
            (12, 1, "Second Semester",    0),
            (12, 1, "Summer Session",     1),
            (13, 2, "First Semester",     0),
            (14, 2, "Second Semester",    0),
            (14, 2, "Summer Session",     1),
            (15, 3, "First Semester",     0),
            (15, 3, "Second Semester",    1),
            (16, 3, "Summer Session",     0),
            (17, 4, "First Semester",     0),
            (17, 4, "Second Semester",    1),
        ],
    },
    "2567": {
        "path": r"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\input\structured\Degreeplan-AI 2567.pdf",
        "contexts": [
            ( 9, 1, "First Semester 1/1", 0),
            ( 9, 1, "First Semester 1/2", 1),
            (10, 1, "Second Semester",    0),
            (10, 1, "Summer Session",     1),
            (11, 2, "First Semester",     0),
            (12, 2, "Second Semester",    0),
            (12, 2, "Summer Session",     1),
            (13, 3, "First Semester",     0),
            (13, 3, "Second Semester",    1),
            (14, 3, "Summer Session",     0),
            (15, 4, "First Semester",     0),
            (15, 4, "Second Semester",    1),
        ],
    },
    "2568": {
        "path": r"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\input\structured\Degreeplan-AI 2568.pdf",
        "contexts": [
            ( 9, 1, "First Semester 1/1", 0),
            ( 9, 1, "First Semester 1/2", 1),
            (10, 1, "Second Semester",    0),
            (10, 1, "Summer Session",     1),
            (11, 2, "First Semester",     0),
            (12, 2, "Second Semester",    0),
            (12, 2, "Summer Session",     1),
            (13, 3, "First Semester",     0),
            (13, 3, "Second Semester",    1),
            (14, 3, "Summer Session",     0),
            (15, 4, "First Semester",     0),
            (15, 4, "Second Semester",    1),
        ],
    },
}

RUNS  = ["รุ่น 1/1", "รุ่น 1/2", "รุ่น 2"]
PLANS = ["ปกติ", "สหกิจ"]
SEM_ORDER = {
    "First Semester 1/1": 1, "First Semester 1/2": 2,
    "First Semester": 1, "Second Semester": 3, "Summer Session": 4,
}
SEMESTER_LABELS = {
    "First Semester 1/1": "ภาคการศึกษาที่ 1 (เทอม 1) กลุ่ม 1/1",
    "First Semester 1/2": "ภาคการศึกษาที่ 1 (เทอม 1) กลุ่ม 1/2",
    "First Semester":     "ภาคการศึกษาที่ 1 (เทอม 1)",
    "Second Semester":    "ภาคการศึกษาที่ 2 (เทอม 2)",
    "Summer Session":     "ภาคการศึกษาฤดูร้อน (Summer)",
}

# =========================================================
# Parser — รองรับทั้ง 2-row header (2565) และ 3-row header (2566+)
# =========================================================

def clean_cell(v):
    if v is None:
        return ""
    # normalize "ปกต ิ" → "ปกติ"
    return " ".join(str(v).split()).replace("ปกต ิ", "ปกติ").strip()

def is_number(s):
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

def detect_header_rows(table):
    """
    คืน index ของ header row สุดท้าย (row ที่มี ปกติ/สหกิจ)
    และ col_map: {col_index: (run, plan)}
    รองรับทั้ง 2-row และ 3-row header
    """
    col_map = {}
    run_row_idx  = None  # row ที่มี "รุ่น"
    plan_row_idx = None  # row ที่มี "ปกติ"/"สหกิจ"

    for ri, row in enumerate(table[:4]):  # ดูแค่ 4 rows แรก
        cells = [clean_cell(c) for c in row]
        if any("รุ่น" in c for c in cells):
            run_row_idx = ri
        if any(c in ("ปกติ", "สหกิจ") for c in cells):
            plan_row_idx = ri
            break  # เจอ plan row แล้ว หยุด

    if run_row_idx is None or plan_row_idx is None:
        return None, col_map

    run_row  = [clean_cell(c) for c in table[run_row_idx]]
    plan_row = [clean_cell(c) for c in table[plan_row_idx]]

    # สร้าง mapping run ต่อ column (forward-fill)
    run_per_col = {}
    current_run = None
    for i, cell in enumerate(run_row):
        if "รุ่น" in cell:
            current_run = cell
        if current_run and i >= 2:
            run_per_col[i] = current_run

    # จับคู่กับ plan
    for i, plan in enumerate(plan_row):
        if plan in ("ปกติ", "สหกิจ") and i in run_per_col:
            col_map[i] = (run_per_col[i], plan)

    return plan_row_idx, col_map  # data เริ่มหลัง plan_row_idx


def parse_table(table):
    if not table or len(table) < 3:
        return []

    header_end, col_map = detect_header_rows(table)
    if not col_map:
        return []

    buckets = {}
    for key in col_map.values():
        if key not in buckets:
            buckets[key] = {"courses": [], "total": None}

    for row in table[header_end + 1:]:
        cells = [clean_cell(c) for c in row]
        if len(cells) < 2:
            continue
        code  = cells[0]
        title = cells[1]

        # skip repeated headers
        if "Course" in code or "รุ่น" in code or "จำนวน" in code:
            continue

        # total row: code & title ว่าง
        if not code and not title:
            for col, key in col_map.items():
                if col < len(cells) and is_number(cells[col]):
                    if not buckets[key]["total"]:
                        buckets[key]["total"] = int(cells[col])
            continue

        # course row
        for col, key in col_map.items():
            if col < len(cells) and is_number(cells[col]):
                existing = [c["code"] for c in buckets[key]["courses"]]
                if code not in existing and code:
                    buckets[key]["courses"].append({
                        "code": code,
                        "title": title,
                        "credits": int(cells[col]),
                    })

    result = []
    for run in RUNS:
        for plan in PLANS:
            key = (run, plan)
            if key in buckets and buckets[key]["courses"]:
                total = buckets[key]["total"] or sum(c["credits"] for c in buckets[key]["courses"])
                result.append({"run": run, "plan": plan,
                               "courses": buckets[key]["courses"], "total": total})
    return result

# =========================================================
# Markdown builder
# =========================================================

def build_markdown(academic_year, all_entries):
    lines = []
    lines.append(f"# แผนการเรียนสาขาวิศวกรรมปัญญาประดิษฐ์และวิทยาการข้อมูล ปี {academic_year}")
    lines.append("")
    lines.append(f"> ข้อมูลจากหลักสูตรปริญญาตรี คณะวิศวกรรมศาสตร์ ปีการศึกษา {academic_year}")
    lines.append("> จำนวนหน่วยกิตตลอดหลักสูตร 136 หน่วยกิต")
    lines.append("")
    lines.append("---")

    all_entries.sort(key=lambda e: (e["year"], SEM_ORDER.get(e["semester"], 9)))

    current_year = None
    current_sem  = None

    for entry in all_entries:
        year     = entry["year"]
        sem      = entry["semester"]
        sections = entry["sections"]
        if not sections:
            continue

        if year != current_year:
            lines.append(f"\n\n## ปีที่ {year}")
            current_year = year
            current_sem  = None

        if sem != current_sem:
            label = SEMESTER_LABELS.get(sem, sem)
            lines.append(f"\n### {label}")
            current_sem = sem

        for sec in sections:
            lines.append(f"\n#### {sec['run']} (แผน{sec['plan']})")
            lines.append("รายวิชา:")
            for c in sec["courses"]:
                lines.append(f"- {c['code']} {c['title']} ({c['credits']} หน่วยกิต)")
            lines.append(f"รวมหน่วยกิต: {sec['total']}")

    return "\n".join(lines)

# =========================================================
# Main
# =========================================================

def convert(academic_year):
    cfg  = YEAR_CONFIG[academic_year]
    path = cfg["path"]
    #out  = f"/mnt/user-data/outputs/degreeplan_AI_{academic_year}_structured.md"
    out = rf"C:\Graduate Project\AIDA-chatbot\backend\database\preprocess\output\structured\degreeplan{academic_year}_clean.txt"
    
    print(f"\n{'='*55}")
    print(f"  ปีการศึกษา {academic_year}  ←  {os.path.basename(path)}")
    print(f"{'='*55}")

    all_entries = []
    with pdfplumber.open(path) as pdf:
        total_pages = len(pdf.pages)
        for (page_num, year, sem, t_idx) in cfg["contexts"]:
            pi = page_num - 1
            if pi >= total_pages:
                print(f"  ⚠️  หน้า {page_num} เกิน ({total_pages} total)")
                continue
            tables = pdf.pages[pi].extract_tables()
            if t_idx >= len(tables):
                print(f"  ⚠️  p{page_num} ไม่มีตาราง[{t_idx}] (มีแค่ {len(tables)})")
                continue
            sections = parse_table(tables[t_idx])
            all_entries.append({"year": year, "semester": sem, "sections": sections})
            n = sum(len(s["courses"]) for s in sections)
            status = "✓" if sections else "⚠ empty"
            print(f"  p{page_num}[t{t_idx}] ปีที่{year} {sem[:14]:14s} → {len(sections)} groups, {n} courses {status}")

    md = build_markdown(academic_year, all_entries)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    lines = md.count("\n")
    print(f"\n  ✅  บันทึก: {out}")
    print(f"      ขนาด: {len(md):,} ตัวอักษร, {lines:,} บรรทัด")
    return out


if __name__ == "__main__":
    target_years = sys.argv[1:] if len(sys.argv) > 1 else list(YEAR_CONFIG.keys())
    outputs = []
    for y in target_years:
        if y not in YEAR_CONFIG:
            print(f"ไม่รู้จักปี: {y}  (รองรับ: {list(YEAR_CONFIG.keys())})")
            continue
        outputs.append(convert(y))
    print(f"\n{'='*55}")
    print(f"✅  รวมทั้งหมด {len(outputs)} ไฟล์")
