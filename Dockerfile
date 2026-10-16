# ── Etapa 1: build del frontend ──
FROM node:26-alpine AS frontend-builder
WORKDIR /app/frontend
COPY Frontend/package.json Frontend/package-lock.json ./
RUN npm ci
COPY Frontend/ .
RUN npm run build

# ── Etapa 2: runtime del backend ──
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Usuario sin privilegios: el proceso no debe correr como root.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home app

COPY --chown=app:app main.py log-config.json ./
COPY --chown=app:app Backend/ Backend/
COPY --from=frontend-builder --chown=app:app /app/frontend/dist Frontend/dist
COPY --chown=app:app img/ img/

# Directorios de escritura (logos, plantillas y facturas generadas).
RUN mkdir -p facturas logos plantillas && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "log-config.json"]
