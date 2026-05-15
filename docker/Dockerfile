FROM python:3.11-slim AS base

FROM base AS engine
RUN apt-get update && apt-get install -y \
    libqt5core5a libqt5gui5 libqt5network5 libqt5concurrent5 libqt5xml5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "engine.main"]