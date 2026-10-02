FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stub_llm /app/stub_llm

EXPOSE 8001

CMD ["uvicorn", "stub_llm.main:app", "--host", "0.0.0.0", "--port", "8001"]
