FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/backend/

RUN apt-get update && apt-get install -y docker.io && apt-get clean

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.api_server:app", "--host", "0.0.0.0", "--port", "8000"]