FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-web.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY backend/ ./backend/
COPY ai/recommendation_engine.py ./ai/recommendation_engine.py
COPY ai/models/*.json ./ai/models/
COPY data/dataset/ ./data/dataset/
COPY --from=frontend /build/dist ./frontend/dist
RUN DB_ENGINE=sqlite DJANGO_DEBUG=true python backend/manage.py collectstatic --noinput \
    && useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
ENV DJANGO_SETTINGS_MODULE=config.cloud DJANGO_DEBUG=false
EXPOSE 10000
CMD ["python", "backend/serve_cloud.py"]
