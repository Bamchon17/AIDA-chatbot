# 1. ใช้ Python 3.10 เวอร์ชันเบาบาง
FROM python:3.10-slim

# 2. ตั้งค่าพื้นที่ทำงานในเซิร์ฟเวอร์
WORKDIR /app

# 3. ติดตั้งไลบรารีทั้งหมด
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. ก๊อปปี้ไฟล์หลังบ้านทั้งหมดของเราลงไป
COPY . .

# 5. แก้ปัญหา Permission เวลา AI พยายามดาวน์โหลดโมเดล
ENV TRANSFORMERS_CACHE=/tmp
ENV HF_HOME=/tmp

# 6. 🚨 สำคัญมาก: Hugging Face บังคับให้แอปทำงานบนพอร์ต 7860 เท่านั้น!
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]