FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src
WORKDIR /app

FROM base AS engine
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "engine.main"]

FROM base AS notebook
COPY requirements.txt .
# Install engine deps + jupyter
RUN pip install --no-cache-dir -r requirements.txt jupyter
COPY . .
# Expose port 8888 for the web UI
EXPOSE 8888
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=''"]
