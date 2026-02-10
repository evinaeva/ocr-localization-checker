FROM python:3.10-slim

WORKDIR /app

COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# копируем весь репо, чтобы worker видел zip_processor и app/*
COPY . /app

ENV PORT=8080
CMD ["uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8080"]
