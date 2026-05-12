# Build from monorepo root: docker build -f apps/api/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY apps/api/requirements.txt /app/requirements-api.txt
RUN pip install --no-cache-dir -r /app/requirements-api.txt

COPY ai-routing.yaml /app/ai-routing.yaml
COPY apps/api/app /app/apps/api/app
COPY apps/api/alembic /app/apps/api/alembic
COPY apps/api/alembic.ini /app/apps/api/alembic.ini

ENV PYTHONPATH=/app/apps/api
ENV AI_ROUTING_CONFIG_PATH=/app/ai-routing.yaml

EXPOSE 8000
# Railway injects PORT. Must run under a shell so ${PORT:-8000} expands (exec-form uvicorn + $PORT does not).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
