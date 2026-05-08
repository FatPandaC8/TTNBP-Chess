# Dockerfile is used to build image
FROM python:3.11-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Enable stdout/stderr logging immediately
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy dependency file first for better Docker cache usage
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Allow importing from src/
ENV PYTHONPATH=/app/src

# Default command
CMD ["python", "-m", "engine.main"]