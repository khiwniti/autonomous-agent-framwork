# Multi-stage Dockerfile for Autonomous Agent System
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml ./

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry lock \
    && poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim

# Set labels
LABEL maintainer="Autonomous Agent Team"
LABEL version="1.0.0"
LABEL description="Autonomous Software Development Agent System"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    AGENT_ENV=production \
    SECURITY_LEVEL=high

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r agent && useradd -r -g agent -u 1001 agent

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=agent:agent src/ ./src/
COPY --chown=agent:agent pyproject.toml ./
COPY --chown=agent:agent start.sh ./

# Create necessary directories
RUN mkdir -p logs .checkpoints .secrets && \
    chown -R agent:agent /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER agent

# Expose ports
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["python", "-m", "uvicorn"]

# Default command
CMD ["agent.api.rest:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
