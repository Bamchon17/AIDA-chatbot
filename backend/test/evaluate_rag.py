"""
test_ragas_eval.py — RAGAS Evaluation สำหรับ AIDA RAG Pipeline
Path: /Users/aoyrzz/Desktop/AIDA-chatbot/backend/test/test_ragas_eval.py
code นี้ใช้ Test-Driven Development (TDD) approach เพื่อทดสอบทั้งระบบ RAG pipeline 
ตั้งแต่การจำแนกเจตนา การดึงข้อมูลจากฐานความรู้ ไปจนถึงการสร้างคำตอบด้วย LLM และการจัดรูปแบบคำตอบ    

ติดตั้ง dependencies:
    pip install ragas langchain-google-genai

วิธีรัน:
    python backend/test/test_ragas_eval.py
    python backend/test/test_ragas_eval.py --save-report

RAGAS Metrics ที่ใช้:
    Faithfulness        — คำตอบอิงจาก context จริงๆ ไม่ hallucinate  (0–1)
    Answer Relevancy    — คำตอบตรงกับคำถามแค่ไหน                     (0–1)
    Context Precision   — chunks ที่ดึงมาเกี่ยวข้องกับคำถามไหม        (0–1)
    Context Recall      — ดึง chunks ได้ครอบคลุมคำตอบที่ควรจะเป็นไหม  (0–1)
"""

import sys
import os
import json
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "ai_core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "database", "embeddings"))

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"
B="\033[1m";  D="\033[2m";  X="\033[0m"

# ═════════════════════════════════════════════════════════════════════════════
# TEST DATASET สำหรับ RAGAS
# format: (user_input, reference_answer)
# reference_answer = คำตอบที่ถูกต้องสำหรับ Context Recall
# ─────────────────────────────────────────────────────────────────────────────
# เลือกเฉพาะ query ที่ต้องการ retrieval จริงๆ (ไม่ใช่ canned)
# ═════════════════════════════════════════════════════════════════════════════
EVAL_DATASET = [
    {
        "user_input":       "ค่าเทอมปี 1 เท่าไหร่ครับ",
        "reference":        "ค่าเทอมปี 1 เทอม 1/1 ประมาณ 25,380 บาท และมีค่าใช้จ่ายเพิ่มเติม 3,000 บาท",
    },
    {
        "user_input":       "ปี 1 ทั้งปีต้องเตรียมเงินกี่บาท",
        "reference":        "ปี 1 ทั้งปีต้องเตรียมเงินประมาณ 99,580 บาท รวมทุกเทอม",
    },
    {
        "user_input":       "ในสาขามีอาจารย์กี่คน และมีใครบ้าง",
        "reference":        "สาขา AIDA มีอาจารย์ประจำ 4 ท่าน",
    },
    {
        "user_input":       "วิชา AIE455 สอนเรื่องอะไร",
        "reference":        "AIE455 คือวิชา Natural Language Processing",
    },
    {
        "user_input":       "สหกิจศึกษาต้องมีเกรดเฉลี่ยเท่าไหร่",
        "reference":        "ต้องมีเกรดเฉลี่ยสะสมตั้งแต่ 2.75 ขึ้นไป ณ สิ้นปีที่ 2",
    },
    {
        "user_input":       "Huawei เป็น MOU กับสาขาไหม",
        "reference":        "Huawei Technologies Company Limited เป็น MOU กับสาขา",
    },
    {
        "user_input":       "บริษัท Mango Consultant ทำเกี่ยวกับอะไร",
        "reference":        "MANGO CONSULTANT พัฒนาซอฟต์แวร์บริหารโครงการ Mango ERP",
    },
    {
        "user_input":       "เรียนจบ AI & Data Science ทำงานอะไรได้บ้าง",
        "reference":        "สามารถทำงานด้าน Machine Learning Engineer, Data Scientist, AI Developer",
    },
    {
        "user_input":       "ถ้าเกรดเฉลี่ยไม่ถึง 2.75 จะฝึกงานได้ไหม",
        "reference":        "ไม่สามารถเข้าร่วมสหกิจศึกษาได้ แต่สามารถฝึกงานทั่วไปแทนได้",
    },
    {
        "user_input":       "มี MOU กับบริษัทที่ทำเรื่อง Robot ไหม",
        "reference":        "มี เช่น DNA ROBOTICS และ IIS AUTOMATION ที่ทำเกี่ยวกับหุ่นยนต์",
    },
]


def load_pipeline():
    """โหลด AIDA pipeline components"""
    print(f"  {D}กำลังโหลด AIDA pipeline...{X}")
    try:
        import intent_classifier  as ic_mod
        import rag_handler        as rh_mod
        import llm_interface      as li_mod
        import response_formatter as rf_mod
        from rag_handler import CLARIFICATION_NEEDED, CURRICULUM_CLARIFY_RESPONSE

        clf = ic_mod.ThaiIntentClassifier()
        clf.load()
        rag = rh_mod.RAGHandler()
        llm = li_mod.LLMInterface()
        RF  = rf_mod.ResponseFormatter

        print(f"  {G}✓{X}  Pipeline โหลดสำเร็จ")
        return clf, rag, llm, RF, CLARIFICATION_NEEDED, CURRICULUM_CLARIFY_RESPONSE

    except Exception as e:
        print(f"  {R}✗{X}  Pipeline โหลดล้มเหลว: {e}")
        return None


def run_pipeline_for_eval(query, clf, rag, llm, RF, CLARIFICATION_NEEDED, CURRICULUM_CLARIFY_RESPONSE):
    """
    รัน AIDA pipeline แล้วคืน:
    - response_text   : คำตอบสุดท้าย (display_text)
    - retrieved_chunks: list of chunk strings ที่ดึงมา
    """
    intent_result = clf.predict(query)

    early = RF.handle_no_retrieval(intent_result)
    if early:
        return early.get("display_text", ""), []

    chunks = rag.retrieve(query, intent_result)

    if chunks is CLARIFICATION_NEEDED:
        return CURRICULUM_CLARIFY_RESPONSE.get("display_text", ""), []

    chunk_texts = [c["text"] for c in chunks] if chunks else []

    llm_raw = llm.generate_response(query, chunks, intent_result)
    final   = RF.format_output(llm_raw, intent_result)
    response_text = final.get("display_text", "")

    return response_text, chunk_texts


def run_ragas_evaluation(eval_dataset_records, save_report=False):
    """
    รัน RAGAS evaluation — รองรับทั้ง ragas <0.2 (Dataset) และ >=0.2 (EvaluationDataset)
    """
    print(f"\n  {D}กำลัง import RAGAS...{X}")

    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(f"  {R}✗{X}  ไม่พบ GEMINI_API_KEY ใน .env")
        return None

    try:
        import ragas
        ragas_version = getattr(ragas, "__version__", "0.0.0")
        print(f"  {D}ragas version: {ragas_version}{X}")
    except ImportError:
        print(f"  {R}✗{X}  ไม่พบ ragas — รัน: pip install ragas")
        return None

    # ── ตรวจ version แล้วเลือก API ──────────────────────────────────────────
    from packaging.version import Version
    try:
        is_new_api = Version(ragas_version) >= Version("0.2.0")
    except Exception:
        is_new_api = False

    if is_new_api:
        return _eval_new_api(eval_dataset_records, api_key)
    else:
        return _eval_old_api(eval_dataset_records, api_key)


def _eval_new_api(eval_dataset_records, api_key):
    """ragas >= 0.2 — ใช้ EvaluationDataset + LangchainLLMWrapper"""
    print(f"  {D}ใช้ New API (ragas >= 0.2){X}")
    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
        # ragas 0.4+ ย้าย metrics ไปที่ collections
        try:
            from ragas.metrics.collections import (
                Faithfulness,
                ResponseRelevancy,
                LLMContextPrecisionWithReference,
                LLMContextRecall,
            )
        except ImportError:
            from ragas.metrics import (
                Faithfulness,
                ResponseRelevancy,
                LLMContextPrecisionWithReference,
                LLMContextRecall,
            )
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

        # LLM สำหรับ evaluate (Faithfulness, ContextPrecision, ContextRecall)
        chat_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.0,
        )
        evaluator_llm = LangchainLLMWrapper(chat_llm)

        # Embeddings สำหรับ ResponseRelevancy (cosine similarity)
        embeddings = LangchainEmbeddingsWrapper(
            GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=api_key,
            )
        )
        print(f"  {G}✓{X}  Gemini LLM + Embeddings พร้อม")

        samples = [
            SingleTurnSample(
                user_input         = r["user_input"],
                response           = r["response"],
                retrieved_contexts = r["retrieved_contexts"],
                reference          = r["reference"],
            )
            for r in eval_dataset_records
        ]
        dataset = EvaluationDataset(samples=samples)

        print(f"\n  {D}evaluate {len(samples)} samples... (ใช้เวลา 2-5 นาที){X}\n")
        return evaluate(
            dataset=dataset,
            metrics=[
                Faithfulness(),
                ResponseRelevancy(),
                LLMContextPrecisionWithReference(),
                LLMContextRecall(),
            ],
            llm=evaluator_llm,
            embeddings=embeddings,   # ← ต้องส่งด้วย ป้องกัน OpenAI fallback
        )
    except Exception as e:
        print(f"  {R}✗{X}  New API error: {e}")
        return None


def _eval_old_api(eval_dataset_records, api_key):
    """ragas < 0.2 — ใช้ datasets.Dataset"""
    print(f"  {D}ใช้ Old API (ragas < 0.2){X}")
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from langchain_google_genai import ChatGoogleGenerativeAI

        os.environ["GOOGLE_API_KEY"] = api_key
        evaluator_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
        )
        print(f"  {G}✓{X}  Gemini evaluator พร้อม (old API)")

        data = {
            "question":    [r["user_input"]         for r in eval_dataset_records],
            "answer":      [r["response"]            for r in eval_dataset_records],
            "contexts":    [r["retrieved_contexts"]  for r in eval_dataset_records],
            "ground_truth":[r["reference"]           for r in eval_dataset_records],
        }
        dataset = Dataset.from_dict(data)

        print(f"\n  {D}evaluate {len(data['question'])} samples... (ใช้เวลา 2-5 นาที){X}\n")
        return evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
            llm=evaluator_llm,
        )
    except ImportError as e:
        print(f"  {R}✗{X}  Old API error: {e}")
        print(f"  {Y}รัน: pip install datasets langchain-google-genai{X}")
        return None
    except Exception as e:
        print(f"  {R}✗{X}  {e}")
        return None


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--save-report", action="store_true")
    args, _ = p.parse_known_args()

    print(f"\n{B}{C}{'═'*64}{X}")
    print(f"{B}{C}  AIDA — RAGAS Evaluation{X}")
    print(f"{B}{C}{'═'*64}{X}")
    print(f"{D}  วันที่: {datetime.now().strftime('%Y-%m-%d %H:%M')}{X}")
    print(f"{D}  Metrics: Faithfulness | Answer Relevancy | Context Precision | Context Recall{X}")

    # โหลด pipeline
    print()
    result = load_pipeline()
    if not result:
        return
    clf, rag, llm, RF, CLARIFICATION_NEEDED, CURRICULUM_CLARIFY_RESPONSE = result

    # รัน AIDA pipeline สำหรับทุก query และเก็บ output
    print()
    print(f"{B}── Step 1: รัน AIDA pipeline เก็บ responses + contexts ──{X}")
    eval_records = []

    for item in EVAL_DATASET:
        query = item["user_input"]
        print(f"  {D}Q: {query[:60]}{X}")
        try:
            response_text, chunk_texts = run_pipeline_for_eval(
                query, clf, rag, llm, RF,
                CLARIFICATION_NEEDED, CURRICULUM_CLARIFY_RESPONSE
            )
            eval_records.append({
                "user_input":         query,
                "response":           response_text,
                "retrieved_contexts": chunk_texts,
                "reference":          item["reference"],
            })
            print(f"    {G}✓{X}  {len(chunk_texts)} chunks | {response_text[:60]}…")
        except Exception as e:
            print(f"    {R}✗{X}  Error: {e}")

    print(f"\n  รวบรวมได้ {len(eval_records)}/{len(EVAL_DATASET)} samples")

    # รัน RAGAS
    print()
    print(f"{B}── Step 2: RAGAS Evaluation ──{X}")
    ragas_result = run_ragas_evaluation(eval_records, save_report=args.save_report)

    if ragas_result is None:
        return

    # แสดงผล
    print(f"\n{B}{C}{'═'*64}{X}")
    print(f"{B}{C}  RAGAS Results{X}")
    print(f"{B}{C}{'═'*64}{X}")

    scores = {}
    # new API: result เป็น dict-like object ที่ key เป็น metric name ใหม่
    # old API: result เป็น dict ที่ key เป็นชื่อ metric เดิม
    key_map = {
        # new API keys
        "faithfulness":       "faithfulness",
        "response_relevancy": "answer_relevancy",
        "llm_context_precision_with_reference": "context_precision",
        "context_recall":     "context_recall",
        # old API keys
        "answer_relevancy":   "answer_relevancy",
        "context_precision":  "context_precision",
    }
    for raw_key, display_key in key_map.items():
        val = None
        try:
            val = ragas_result[raw_key]
        except (KeyError, TypeError):
            pass
        if val is not None and display_key not in scores:
            if isinstance(val, list):
                val = sum(v for v in val if v is not None) / max(len([v for v in val if v is not None]), 1)
            scores[display_key] = float(val)

    labels = {
        "faithfulness":      "Faithfulness        (ไม่ hallucinate)",
        "answer_relevancy":  "Answer Relevancy    (ตรงคำถาม)",
        "context_precision": "Context Precision   (chunks เกี่ยวข้อง)",
        "context_recall":    "Context Recall      (ดึงได้ครบ)",
    }

    print()
    for key, label in labels.items():
        score = scores.get(key)
        if score is None or (isinstance(score, float) and score != score):  # None or NaN
            print(f"  {label:<40} {Y}N/A{X}  (ไม่มีข้อมูล)")
            continue
        bar_len = int(score * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        col = G if score >= 0.8 else Y if score >= 0.6 else R
        print(f"  {label:<40} {col}{score:.4f}{X}  [{bar}]")

    valid = [v for v in scores.values() if v is not None and v == v]  # exclude None and NaN
    overall = sum(valid) / len(valid) if valid else 0.0
    col = G if overall >= 0.8 else Y if overall >= 0.6 else R
    print(f"\n  {B}Overall Average{X}{'':>30} {col}{overall:.4f}{X}")

    # ความหมายของแต่ละ metric
    print(f"\n  {D}คำอธิบาย:{X}")
    print(f"  {D}  Faithfulness      > 0.8 = AIDA ไม่แต่งข้อมูลเอง ✓{X}")
    print(f"  {D}  Answer Relevancy  > 0.8 = คำตอบตรงกับคำถามที่ถาม ✓{X}")
    print(f"  {D}  Context Precision > 0.8 = chunks ที่ดึงมาล้วนเกี่ยวข้อง ✓{X}")
    print(f"  {D}  Context Recall    > 0.8 = ดึง chunks ที่จำเป็นมาได้ครบ ✓{X}")

    # Save report
    if args.save_report:
        out_dir = os.path.join(PROJECT_ROOT, "backend", "test", "reports")
        os.makedirs(out_dir, exist_ok=True)
        fname = os.path.join(
            out_dir,
            f"ragas_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )
        report = {
            "timestamp":       datetime.now().isoformat(),
            "scores":          {k: float(v) for k, v in scores.items()},
            "overall_average": float(overall),
            "samples":         len(eval_records),
            "eval_records":    eval_records,
        }
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  {G}✓{X}  บันทึก: {fname}")

    print()


if __name__ == "__main__":
    main()