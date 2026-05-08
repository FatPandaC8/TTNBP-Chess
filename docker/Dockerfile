# Choose Python version
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy requirements and setting
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project
COPY . .

# It is not working
# # Thêm Python path để import src/engine dễ dàng
# ENV PYTHONPATH=/app/src

# # Mặc định mở Python interactive shell
# CMD ["python3"]
