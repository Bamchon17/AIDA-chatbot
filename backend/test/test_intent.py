import sys
import os
import json  # <--- เพิ่ม import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ai_core.intent_classifier import ThaiIntentClassifier

def run_quick_tests(clf):
    print("=" * 55)
    print(" 🚀 Intent Classifier — Fast JSON Test")
    print(" พิมพ์ 'q' เพื่อออกและเซฟไฟล์ JSON ส่งให้เพื่อน") # <--- เปลี่ยนข้อความนิดหน่อย
    print("=" * 55)

    # 1. สร้าง List มารอเก็บผลลัพธ์ทั้งหมด
    all_results = []

    while True:
        query = input("\n📝 Query : ").strip()
        
        if query.lower() in ["q"]:
            # 2. เมื่อกด q ให้ทำการบันทึกไฟล์ก่อนปิดโปรแกรม
            if all_results:  # เช็คก่อนว่ามีข้อมูลให้เซฟไหม
                filename = "export_intent_data.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=4)
                
                print(f"\n✅ บันทึกข้อมูล {len(all_results)} รายการ ลงไฟล์ '{filename}' เรียบร้อย!")
            else:
                print("\n⚠️ ไม่มีข้อมูลให้บันทึก (ไม่ได้พิมพ์คำถามเลย)")

            print("👋 ออกจากโปรแกรม")
            sys.exit(0)
            
        if not query:
            continue

        # 3. ใช้ predict() จะได้ค่ากลับมาเป็น Dictionary เพื่อให้เก็บลง List ได้ง่ายๆ
        dict_output = clf.predict(query)
        
        # นำ Dictionary ที่ได้ ไปต่อท้ายใน List
        all_results.append(dict_output)
        
        # 4. แปลง Dictionary กลับเป็น JSON String สวยๆ เพื่อพริ้นต์ออกจอให้คุณดูเหมือนเดิม
        json_output = json.dumps(dict_output, ensure_ascii=False, indent=2)
        
        print("\n--- JSON Output ---")
        print(json_output)
        print("-" * 19)

if __name__ == "__main__":
    clf = ThaiIntentClassifier()
    clf.load()
    run_quick_tests(clf)