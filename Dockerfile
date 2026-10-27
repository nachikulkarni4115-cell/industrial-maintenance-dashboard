FROM python:3.12-slim

# UID 999 matches k8s runAsUser. Group 10001 matches the existing PVC host dir (GID 10001, mode 0770).
RUN groupadd -r -g 10001 appgrp \
 && useradd -r -u 999 -g appgrp -d /app -s /sbin/nologin appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY wsgi.py .

# Persistent data mount point for SQLite (/data/maintenance.db)
RUN mkdir -p /data /app/instance && chown -R appuser:appgrp /app /data

USER appuser

ENV FLASK_CONFIG=production
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////data/maintenance.db

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -f http://127.0.0.1:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2", "--timeout", "60", "wsgi:app"]
