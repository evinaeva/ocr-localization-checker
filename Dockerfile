FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run по умолчанию использует порт 8080
ENV PORT=8080

CMD ["uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8080"]
