ARG BUILD_FROM=python:3.12-slim-bookworm
FROM ${BUILD_FROM}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8080

WORKDIR /opt/finanz
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app

EXPOSE 8080
CMD ["python", "-m", "app"]
