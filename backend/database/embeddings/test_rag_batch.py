import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from kb_loader import KnowledgeBaseLoader

def run_batch_test():
    print("--- AIDA RAG Batch Diagnostic Test ---")
    
    try:
        kb = KnowledgeBaseLoader()
        index_name = "combined_embedded"
    except Exception as e:
        print(f"[ERROR] Failed to load KnowledgeBaseLoader: {e}")
        return
    
    # ชุดคำถามและ "หมวดหมู่ที่ถูกต้อง" ที่ควรจะดึงมาได้
    test_cases = [
        {
            "query": "ปี 1 เทอม 1 ต้องเรียนวิชาอะไรบ้าง",
            "expected_category": "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร]"  # ไม่มีช่องว่างระหว่าง ปี กับ 2568
        },
        {
            "query": "วิชา AIE311 เรียนเกี่ยวกับอะไร",
            "expected_category": "[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา]"
        },
        {
            "query": "ค่าเทอมปี 1 เทอม 1 แบบจ่ายเต็มเท่าไหร่",
            "expected_category": "[หมวดหมู่: ค่าเทอมและการเงิน]"
        },
        {
            "query": "กู้ กยศ ปี 2 ต้องจ่ายเพิ่มเท่าไหร่",
            "expected_category": "[หมวดหมู่: ค่าเทอมและการเงิน]"
        },
        {
            "query": "อาจารย์ภูมิพัฒเชี่ยวชาญด้านอะไร",
            "expected_category": "[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]"
        },
        {
            "query": "มีอาจารย์คนไหนเชี่ยวชาญด้าน Computer Vision บ้าง",
            "expected_category": "[หมวดหมู่: ข้อมูลอาจารย์และบุคลากร]"
        },
        {
            "query": "สหกิจศึกษากับฝึกงานปกติต่างกันอย่างไร",
            "expected_category": "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]"
        },
        {
            "query": "สหกิจศึกษาต้องไปฝึกตอนปีไหน",
            "expected_category": "[หมวดหมู่: สหกิจศึกษา/การฝึกงาน]"
        },
        {
            "query": "บริษัท Softnix ทำเกี่ยวกับอะไร",
            "expected_category": "[หมวดหมู่: เครือข่ายบริษัท/MOU]"
        },
        {
            "query": "สาขานี้เรียนจบไปทำงานอะไรได้บ้าง",
            "expected_category": "[หมวดหมู่: ข้อมูลสาขาวิชา]"  # detect_category จะดัก "สาขา" → ข้อมูลสาขาวิชา
        }
    ]

    passed = 0
    failed = 0
    failed_cases = []

    print(f"Starting diagnosis for {len(test_cases)} queries...\n")
    print("=" * 60)

    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        expected = test["expected_category"]
        
        print(f"Test [{i}/{len(test_cases)}]: {query}")
        
        # ดึงมาแค่ Top 3 เพื่อดูว่ามีเนื้อหาที่ตรงหมวดหมู่หลุดมาบ้างไหม
        results = kb.search(query=query, save_name=index_name, top_k=3)
        
        is_pass = False
        top_chunks = []
        
        for res in results:
            chunk_text = res['chunk']
            top_chunks.append(chunk_text)
            # รองรับทั้ง exact match และ prefix match
            # (degree plan tag อาจมีปีต่อท้าย เช่น "[หมวดหมู่: แผนการเรียน/โครงสร้างหลักสูตร ปี2568]")
            if expected in chunk_text or any(expected in line for line in chunk_text.split('\n') if line.startswith(expected)):
                is_pass = True
                break
        
        if is_pass:
            print("[PASS]")
            passed += 1
        else:
            print("[FAIL] Wrong context retrieved")
            failed += 1
            failed_cases.append({
                "query": query,
                "expected": expected,
                "actual_top_1": top_chunks[0] if top_chunks else "No results found"
            })
        print("-" * 60)

    # สรุปผล
    print("\n" + "=" * 20 + " TEST SUMMARY " + "=" * 20)
    print(f"Total Queries : {len(test_cases)}")
    print(f"Passed        : {passed}")
    print(f"Failed        : {failed}")

    if failed > 0:
        print("\n" + "=" * 17 + " FAILED CASES ANALYSIS " + "=" * 18)
        for fail in failed_cases:
            print(f"Query: {fail['query']}")
            print(f"Expected to find: {fail['expected']}")
            print(f"But actual Top 1 chunk was:")
            # พิมพ์ออกมาแค่ 250 ตัวอักษรแรกเพื่อดูว่าเป็นข้อมูลหมวดไหนที่แทรกเข้ามา
            print(f"{fail['actual_top_1'][:250]}...")
            print("-" * 60)

if __name__ == "__main__":
    run_batch_test()