FROM python:3.11-slim AS base

FROM base AS engine
# 1. Install system dependencies (Qt libraries and make) all in one stage
RUN apt-get update && apt-get install -y \
    libqt5core5a libqt5gui5 libqt5network5 libqt5concurrent5 libqt5xml5 \
    make \
    && rm -rf /var/lib/apt/lists/*

# 2. Set a dedicated working directory so local files don't clash with system roots
WORKDIR /app

# 3. Copy Python dependencies first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your application code safely into /app
COPY . .

CMD ["python", "-m", "engine.main"]
