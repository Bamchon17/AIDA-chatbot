import os
import pandas as pd
import plotly.graph_objects as go
from datasets import Dataset
from dotenv import load_dotenv
from pathlib import Path

# 1. ใช้ RAGAS 0.1.22 (ดึงจาก metrics ตรงๆ และใช้ตัวพิมพ์เล็ก)
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
)

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("[ERROR] ไม่พบ GROQ_API_KEY ในไฟล์ .env")

print("="*60)
print("📊 AIDA RAG Evaluation with RAGAS (Stable Version 0.1.22)")
print("="*60)

print("[INFO] กำลังตั้งค่ากรรมการ (Judge) Llama-3.3 และโมเดล Embedding...")
# สร้างโมเดล Langchain ตามปกติ (เวอร์ชันนี้มันคุยกันรู้เรื่องครับ)
groq_llm = ChatGroq(model_name="llama-3.3-70b-versatile", api_key=api_key, temperature=0)
hf_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# 2. ใช้ชุดข้อมูล Key มาตรฐานเดิม
data_samples = {
    "question": [
        "วิชา AIE311 เรียนเกี่ยวกับอะไร",
        "สหกิจศึกษาต้องไปฝึกตอนปีไหน"
    ],
    "answer": [
        "วิชา AIE311 เรียนเกี่ยวกับโครงสร้างข้อมูลและอัลกอริทึม",
        "สหกิจศึกษาต้องไปฝึกตอนปีที่ 4"
    ],
    "contexts": [
        ["[หมวดหมู่: รายวิชาและคำอธิบายรายวิชา] AIE311 โครงสร้างข้อมูลและอัลกอริทึม (Data Structures and Algorithms) ศึกษาเกี่ยวกับโครงสร้างข้อมูลแบบต่างๆ..."],
        ["[หมวดหมู่: สหกิจศึกษา/การฝึกงาน] สำหรับสหกิจศึกษาในคณะวิศวกรรมศาสตร์ นักศึกษาจะต้องไปฝึกตอนปีที่ 4 ภาคการศึกษาที่ 1..."]
    ],
    "ground_truth": [
        "เรียนเกี่ยวกับโครงสร้างข้อมูลและอัลกอริทึม",
        "นักศึกษาต้องไปฝึกงานสหกิจศึกษาตอนชั้นปีที่ 4 ภาคการศึกษาที่ 1"
    ]
}

dataset = Dataset.from_dict(data_samples)

print("[INFO] เริ่มกระบวนการประเมินผล (อาจใช้เวลาสักครู่)...")
# 3. รวบตึงส่ง LLM และ Embeddings ในคำสั่งเดียว
result = evaluate(
    dataset=dataset,
    metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
    llm=groq_llm,
    embeddings=hf_embeddings
)

df_result = result.to_pandas()
print("\n📋 ผลคะแนนรายข้อ:")
print(df_result[['question', 'context_precision', 'context_recall', 'faithfulness', 'answer_relevancy']])

print("\n🏆 คะแนนเฉลี่ยรวมของระบบ:")
print(result)

print("\n[INFO] กำลังสร้างกราฟ Radar Chart...")
categories = ['Context Precision', 'Context Recall', 'Faithfulness', 'Answer Relevancy']
scores = [
    result['context_precision'],
    result['context_recall'],
    result['faithfulness'],
    result['answer_relevancy']
]

fig = go.Figure()

fig.add_trace(go.Scatterpolar(
      r=scores,
      theta=categories,
      fill='toself',
      name='AIDA RAG Performance',
      line_color='cyan',
      fillcolor='rgba(0, 255, 255, 0.3)'
))

fig.update_layout(
  polar=dict(
    radialaxis=dict(
      visible=True,
      range=[0, 1] 
    )),
  showlegend=True,
  title="AIDA RAG System Evaluation (RAGAS Metrics)",
  template="plotly_dark" 
)

output_file = "rag_evaluation_chart.html"
fig.write_html(output_file)
print(f"✨ เสร็จสิ้น! กราฟถูกบันทึกไว้ที่ไฟล์: {os.path.abspath(output_file)}")