ARG BUILD_FROM=python:3.12-slim-bookworm
FROM ${BUILD_FROM}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8080

# Texterkennung und PDF-Lesen für Abrechnungen und Screenshots (läuft lokal, ohne Internet)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/finanz
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app

EXPOSE 8080
CMD ["python", "-m", "app"]
