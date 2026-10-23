FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/scripts:/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY worker /app/worker
COPY api /app/api
COPY pipeline /app/pipeline
COPY corpus /app/corpus
COPY scripts /app/scripts
COPY agents /app/agents
COPY llm /app/llm
COPY prompts /app/prompts
COPY guardrails /app/guardrails

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
