FROM python:3.12-slim

# UID 999 / GID 10001 match the existing Kubernetes PVC permissions.
RUN groupadd -r -g 10001 appgrp \
 && useradd -r -u 999 -g appgrp -d /app -s /usr/sbin/nologin appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY wsgi.py .

# Persistent SQLite database is mounted at /data in Kubernetes.
RUN mkdir -p /data /app/instance \
 && chown -R appuser:appgrp /app /data

USER appuser

ENV FLASK_CONFIG=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/maintenance.db

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
