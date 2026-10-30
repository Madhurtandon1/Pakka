FROM python:3.11-slim
WORKDIR /app

# nginx is the public web server; it serves the pages and proxies the API to uvicorn.
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ocr.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Offline Aadhaar card reading (see requirements-ocr.txt for why --no-deps)
RUN pip install --no-cache-dir -r requirements-ocr.txt \
 && pip install --no-cache-dir --no-deps "rapidocr_onnxruntime>=1.2.3,<1.5"
COPY . .
RUN python eval/run_eval.py && python eval/merchant_eval.py

# Render (and most hosts) pass the public port in $PORT; locally it falls back to 8000.
EXPOSE 8000
CMD ["bash", "/app/deploy/start.sh"]
