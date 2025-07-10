FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends rsync && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools

COPY app.py .
COPY static/ ./static/

ENV IS_MAIN_WORKER=1

EXPOSE 5050

CMD ["gunicorn", "--workers=1", "--bind=0.0.0.0:5050", "app:app"]
