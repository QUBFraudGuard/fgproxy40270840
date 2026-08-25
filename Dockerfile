# Python screening service — the only service with business logic.
# Built and run as an individual container (no docker-compose)
FROM python:3.12-slim
WORKDIR /app

# Install dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Configurable threshold; default flags amounts over 10000.
EXPOSE 8080

# app.py runs Flask on 0.0.0.0:8070.
CMD ["python", "app.py"]
