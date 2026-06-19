# Dockerfile for deploying the Dev Agent A2A Server to Cloud Run
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency definition
COPY dev-agent/pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry lock \
    && poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    AGENT_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r agent && useradd -r -g agent -u 1001 agent

WORKDIR /app

# Copy python packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app code
COPY --chown=agent:agent dev-agent/src/ ./src/
COPY --chown=agent:agent dev-agent/pyproject.toml ./
COPY --chown=agent:agent dev-agent/start.sh ./

RUN mkdir -p logs .checkpoints .secrets && \
    chown -R agent:agent /app

USER agent

# Expose container port
EXPOSE 8080

# Run uvicorn using factory option to boot create_a2a_app()
CMD ["sh", "-c", "uvicorn agent.api.a2a_app:create_a2a_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]
