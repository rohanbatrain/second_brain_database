# syntax=docker/dockerfile:1

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY .sbd ./

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' sbduser && chown -R sbduser /app
USER sbduser

# Expose port (default FastAPI port)
EXPOSE 8000

# Set environment for production
ENV DEBUG=false
ENV PYTHON_ENV=production
ENV LOG_LEVEL=info
ENV GUNICORN_CMD_ARGS="--timeout 60 --keep-alive 5"

# Start the application with Uvicorn (with recommended production flags)
CMD ["uvicorn", "src.second_brain_database.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
