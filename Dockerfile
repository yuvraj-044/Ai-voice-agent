# ResumeFlow Interview Studio — Hugging Face Spaces (Docker)
FROM python:3.11-slim

WORKDIR /app

# Non-root user (required by HF Spaces)
RUN useradd -m -u 1000 appuser

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Writable DB location lives inside /app (owned by appuser)
RUN chown -R appuser:appuser /app
USER appuser

ENV PORT=7860 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
