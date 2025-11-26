# syntax=docker/dockerfile:1

# Builder stage
# Builder stage
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /app

# Copy dependency files
COPY config/pyproject.toml config/uv.lock ./

# Copy package source and project metadata so the builder can build the package
# (pyproject.toml references README.md and the package uses a src/ layout)
COPY src/ ./src/
COPY README.md ./

# Install dependencies (including voice extras for production)
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.11-slim AS runtime

# Add labels for better container management
LABEL maintainer="Rohan Batra <contact@rohanbatra.in>"
LABEL org.opencontainers.image.title="Second Brain Database"
LABEL org.opencontainers.image.description="FastAPI-based knowledge management system"
LABEL org.opencontainers.image.version="0.0.4"

# Create non-root user
RUN adduser --disabled-password --gecos '' sbduser

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ffmpeg \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Copy configuration file if it exists (optional)
COPY .sbd* ./

# Set ownership
RUN chown -R sbduser:sbduser /app

# Switch to non-root user
USER sbduser

# Expose port (only for API mode)
EXPOSE 8000

# Environment variables
ENV DEBUG=false \
    PYTHON_ENV=production \
    LOG_LEVEL=info \
    CMD_MODE=api

# Health check - uses Python instead of curl to avoid extra dependencies
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Entrypoint script to support multiple modes
COPY --chown=sbduser:sbduser infra/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (can be overridden)
CMD ["api"]
