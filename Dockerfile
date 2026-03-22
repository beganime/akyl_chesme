# Dockerfile — продакшн сборка AkylChat Backend

# ── Stage 1: Dependencies ──────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Production ────────────────────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Только runtime зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем установленные пакеты из deps стадии
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Создаём непривилегированного пользователя
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Копируем код
COPY --chown=appuser:appgroup . .

# Создаём нужные директории
RUN mkdir -p /app/static /app/downloads /app/logs && \
    chown -R appuser:appgroup /app

USER appuser

# Запускаем через uvicorn с несколькими воркерами
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "info", \
     "--access-log"]