FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EXCEL_AUTO_MAX_UPLOAD_MB=50 \
    EXCEL_AUTO_DATA_DIR=/srv/data

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Utilisateur sans privilèges
RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/data && chown appuser /srv/data
USER appuser
# Données des applications générées : à monter sur un volume persistant.
VOLUME ["/srv/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
