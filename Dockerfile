FROM python:3.11-slim
WORKDIR /app

# nginx is the public web server; it serves the pages and proxies the API to uvicorn.
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python eval/run_eval.py && python eval/merchant_eval.py

# Render (and most hosts) pass the public port in $PORT; locally it falls back to 8000.
EXPOSE 8000
CMD ["bash", "/app/deploy/start.sh"]
