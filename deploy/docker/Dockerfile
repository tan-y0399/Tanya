# Stage 1: build frontend static assets
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com

COPY frontend/ ./
RUN npm run build


# Stage 2: runtime (FastAPI + static frontend)
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-client \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/ ./backend/
COPY tools/ ./tools/
COPY deploy/ ./deploy/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

COPY deploy/docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=40s \
    CMD curl -f http://127.0.0.1:8000/api/v1/system/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
