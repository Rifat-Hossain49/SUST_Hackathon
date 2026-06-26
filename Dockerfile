# QueueStorm Investigator — small, CPU-only, no model weights baked in.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY app ./app

# Run as a non-root user.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Readiness probe hits /health on the active port (respects $PORT for PaaS hosts).
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health',timeout=3).status==200 else 1)"

# Bind 0.0.0.0 and honor $PORT (Render/Railway/Fly inject it).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
