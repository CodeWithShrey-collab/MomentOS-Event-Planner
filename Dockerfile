# Build the React client once; Flask serves these files from the same origin.
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Keep the runtime image limited to Python runtime dependencies and app code.
FROM python:3.12-slim AS runtime
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_SKIP_DOTENV=1 \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    PYTHONPATH=/app/backend
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend-build /build/frontend/dist/ /app/frontend/dist/
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn --chdir backend wsgi:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --worker-class gthread --threads 4 --timeout 90 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100 --error-logfile -"]
