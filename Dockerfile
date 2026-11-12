FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/apps/worker/src \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "mistralai-workflows>=3.10,<4" "httpx>=0.27"

COPY apps ./apps

CMD ["python", "-m", "worker.entrypoints.worker"]
