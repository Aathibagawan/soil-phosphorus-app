FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    PIP_NO_CACHE_DIR=1

# Hugging Face Spaces runs containers as UID 1000; create the same user so the
# SQLite file in /app/data is writable there and everywhere else.
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser frontend ./frontend
COPY --chown=appuser:appuser artifacts ./artifacts
RUN mkdir -p /app/data && chown appuser:appuser /app/data

USER appuser

# 7860 = Hugging Face Spaces default; Render/Railway/Fly inject $PORT.
ENV PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request as u; u.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}/api/health', timeout=4)"

# --proxy-headers so rate limiting sees the real client IP behind the platform proxy.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
