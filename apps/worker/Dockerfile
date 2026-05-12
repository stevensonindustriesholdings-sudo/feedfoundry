# Build from monorepo root: docker build -f apps/worker/Dockerfile .
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/worker/requirements.txt /app/requirements-worker.txt
RUN pip install --no-cache-dir -r /app/requirements-worker.txt

COPY ai-routing.yaml /app/ai-routing.yaml
COPY apps/api/app /app/apps/api/app
COPY apps/worker /app/apps/worker

ENV PYTHONPATH=/app/apps/api:/app/apps/worker
ENV AI_ROUTING_CONFIG_PATH=/app/ai-routing.yaml

WORKDIR /app/apps/worker
CMD ["python", "worker.py"]
