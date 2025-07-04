FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*

COPY app.py .
COPY static ./static

EXPOSE 5050

CMD ["python", "app.py"]
