# ===== STAGE 1: builder =====
FROM python:3.11-slim AS builder

WORKDIR /app

COPY app/requirements.txt .

# Bağımlılıkları wheel olarak derle - production stage'e sadece bunları taşıyacağız
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ===== STAGE 2: production =====
FROM python:3.11-slim

# Root olmayan kullanıcı oluştur
RUN groupadd -r appgroup && useradd -r -g appgroup -m appuser

WORKDIR /app

# Sadece derlenmiş wheel'leri builder stage'inden al
COPY --from=builder /wheels /wheels
COPY app/requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Uygulama kodunu kopyala, sahipliği appuser'a ver
COPY --chown=appuser:appgroup app/app.py .

# curl, healthcheck için gerekli (slim image'de yok, minimal ekliyoruz)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "app.py"]
