FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend:/app/scripts:/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY corpus /app/corpus
COPY scripts /app/scripts

EXPOSE 8002

CMD ["python", "-m", "worker.main"]
