FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY processor /app/processor

WORKDIR /app/backend
ENV PYTHONPATH="/app/backend:/app/processor"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
