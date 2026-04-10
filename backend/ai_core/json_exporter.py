import json
import os

def save_to_json(data_list, filename="export_data.json"):
    """
    ฟังก์ชันสำหรับรับ List ของ Dictionary มาบันทึกเป็นไฟล์ .json
    """
    # ตรวจสอบว่ามีข้อมูลหรือไม่
    if not data_list:
        print("⚠️ ไม่มีข้อมูลให้บันทึก")
        return

    try:
        with open(filename, "w", encoding="utf-8") as f:
            # ensure_ascii=False สำคัญมาก ไม่งั้นภาษาไทยจะกลายเป็นรหัสต่างด้าว
            json.dump(data_list, f, ensure_ascii=False, indent=4)
        
        # หาวิธีบอกเพื่อนว่าไฟล์เซฟไว้ที่ไหน
        full_path = os.path.abspath(filename)
        print(f"\n✅ สร้างไฟล์เสร็จสมบูรณ์!")
        print(f"📁 บันทึกไว้ที่: {full_path}")
        print(f"📊 จำนวนข้อมูลทั้งหมด: {len(data_list)} รายการ")
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการบันทึกไฟล์: {e}")