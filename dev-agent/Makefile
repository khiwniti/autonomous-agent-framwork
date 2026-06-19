# Autonomous Dev Agent - Makefile
# Simplifies installation, development, and deployment

.PHONY: help install install-dev setup clean start stop restart logs test lint format check docker-up docker-down docker-logs shell

# Default target
help:
	@echo "Autonomous Dev Agent - Available Commands"
	@echo "=========================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install      - Install dependencies (checks Python version)"
	@echo "  make install-dev  - Install with dev dependencies"
	@echo "  make setup        - Full setup: Python check + install + Docker"
	@echo "  make clean        - Remove virtual env and cache files"
	@echo ""
	@echo "Development:"
	@echo "  make start        - Start all services (Docker + API)"
	@echo "  make stop         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - View service logs"
	@echo "  make shell        - Open shell in virtual environment"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up    - Start Docker services only"
	@echo "  make docker-down  - Stop Docker services"
	@echo "  make docker-logs  - View Docker container logs"
	@echo ""
	@echo "Quality:"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"
	@echo "  make check        - Run all checks (lint + test)"

# Python version requirements
PYTHON_MIN_VERSION := 3.11
PYTHON_MAX_VERSION := 3.13

# Detect Python
PYTHON := $(shell which python3.11 2>/dev/null || which python3.12 2>/dev/null || which python3)
PYTHON_VERSION := $(shell $(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)

# Check if Poetry is installed
POETRY := $(shell which poetry 2>/dev/null)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

#------------------------------------------------------------------------------
# Setup & Installation
#------------------------------------------------------------------------------

check-python:
	@echo "$(BLUE)Checking Python version...$(NC)"
	@if [ -z "$(PYTHON)" ]; then \
		echo "$(RED)Error: Python not found$(NC)"; \
		echo "Please install Python 3.11 or 3.12:"; \
		echo "  brew install python@3.11"; \
		echo "  # or"; \
		echo "  pyenv install 3.11.11"; \
		exit 1; \
	fi
	@MAJOR=$$($(PYTHON) -c "import sys; print(sys.version_info.major)"); \
	MINOR=$$($(PYTHON) -c "import sys; print(sys.version_info.minor)"); \
	if [ "$$MAJOR" -ne 3 ] || [ "$$MINOR" -lt 11 ] || [ "$$MINOR" -ge 14 ]; then \
		echo "$(RED)Error: Python $(PYTHON_VERSION) is not supported$(NC)"; \
		echo "Required: Python 3.11.x or 3.12.x"; \
		echo ""; \
		echo "Install a compatible version:"; \
		echo "  $(YELLOW)brew install python@3.11$(NC)"; \
		echo "  # or"; \
		echo "  $(YELLOW)pyenv install 3.11.11 && pyenv local 3.11.11$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Python $(PYTHON_VERSION) detected at $(PYTHON)$(NC)"

check-poetry:
	@echo "$(BLUE)Checking Poetry...$(NC)"
	@if [ -z "$(POETRY)" ]; then \
		echo "$(YELLOW)Poetry not found. Installing...$(NC)"; \
		curl -sSL https://install.python-poetry.org | $(PYTHON) -; \
		echo "$(GREEN)✓ Poetry installed$(NC)"; \
		echo "$(YELLOW)Please restart your terminal or run: export PATH=\"$$HOME/.local/bin:$$PATH\"$(NC)"; \
	else \
		echo "$(GREEN)✓ Poetry found at $(POETRY)$(NC)"; \
	fi

install: check-python check-poetry
	@echo "$(BLUE)Installing dependencies...$(NC)"
	@poetry env use $(PYTHON) || true
	@echo "$(BLUE)Updating lock file...$(NC)"
	@poetry lock --no-update
	@poetry install --no-interaction
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-dev: check-python check-poetry
	@echo "$(BLUE)Installing dev dependencies...$(NC)"
	@poetry env use $(PYTHON) || true
	@echo "$(BLUE)Updating lock file...$(NC)"
	@poetry lock --no-update
	@poetry install --with dev --no-interaction
	@echo "$(GREEN)✓ Dev dependencies installed$(NC)"

setup: install docker-up
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@echo "Services running:"
	@echo "  - PostgreSQL (pgvector): localhost:5432"
	@echo "  - Redis: localhost:6379"
	@echo "  - Langfuse: http://localhost:3001"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and configure"
	@echo "  2. Run: make start"
	@echo ""

clean:
	@echo "$(BLUE)Cleaning up...$(NC)"
	@poetry env remove --all 2>/dev/null || true
	@rm -rf .venv
	@rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

#------------------------------------------------------------------------------
# Development
#------------------------------------------------------------------------------

start: docker-up
	@echo "$(BLUE)Starting API server...$(NC)"
	@poetry run python -m src.agent.cli.main serve &
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo ""
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"

stop: docker-down
	@echo "$(BLUE)Stopping services...$(NC)"
	@pkill -f "python -m src.agent.cli.main" 2>/dev/null || true
	@echo "$(GREEN)✓ Services stopped$(NC)"

restart: stop start

logs:
	@docker-compose logs -f

shell:
	@poetry shell

#------------------------------------------------------------------------------
# Docker
#------------------------------------------------------------------------------

docker-up:
	@echo "$(BLUE)Starting Docker services...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)✓ Docker services started$(NC)"
	@echo ""
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@docker-compose ps

docker-down:
	@echo "$(BLUE)Stopping Docker services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✓ Docker services stopped$(NC)"

docker-logs:
	@docker-compose logs -f

docker-rebuild:
	@echo "$(BLUE)Rebuilding Docker images...$(NC)"
	@docker-compose build --no-cache
	@docker-compose up -d
	@echo "$(GREEN)✓ Docker services rebuilt$(NC)"

#------------------------------------------------------------------------------
# Quality
#------------------------------------------------------------------------------

test:
	@echo "$(BLUE)Running tests...$(NC)"
	@poetry run pytest tests/ -v --cov=src --cov-report=html
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-fast:
	@echo "$(BLUE)Running tests (fast mode)...$(NC)"
	@poetry run pytest tests/ -x -q
	@echo "$(GREEN)✓ Tests complete$(NC)"

lint:
	@echo "$(BLUE)Running linters...$(NC)"
	@poetry run ruff check src/ tests/
	@poetry run mypy src/ --ignore-missing-imports
	@echo "$(GREEN)✓ Lint complete$(NC)"

format:
	@echo "$(BLUE)Formatting code...$(NC)"
	@poetry run ruff format src/ tests/
	@poetry run ruff check --fix src/ tests/
	@echo "$(GREEN)✓ Format complete$(NC)"

check: lint test
	@echo "$(GREEN)✓ All checks passed$(NC)"

#------------------------------------------------------------------------------
# Utilities
#------------------------------------------------------------------------------

.env:
	@if [ ! -f .env ]; then \
		echo "$(BLUE)Creating .env from template...$(NC)"; \
		cp .env.example .env 2>/dev/null || echo "# Environment Configuration\n\n# OpenAI\nOPENAI_API_KEY=your-key-here\n\n# Database\nDATABASE_URL=postgresql://postgres:postgres@localhost:5432/agent_db\n\n# Redis\nREDIS_URL=redis://localhost:6379\n\n# Langfuse (optional)\nLANGFUSE_PUBLIC_KEY=\nLANGFUSE_SECRET_KEY=\nLANGFUSE_HOST=http://localhost:3001" > .env; \
		echo "$(YELLOW)Created .env - please configure your API keys$(NC)"; \
	fi

env-check: .env
	@echo "$(BLUE)Checking environment...$(NC)"
	@if grep -q "your-key-here" .env; then \
		echo "$(YELLOW)Warning: OPENAI_API_KEY not configured in .env$(NC)"; \
	else \
		echo "$(GREEN)✓ Environment configured$(NC)"; \
	fi

# Quick start alias
run: start

# Database migrations
db-migrate:
	@echo "$(BLUE)Running database migrations...$(NC)"
	@poetry run alembic upgrade head
	@echo "$(GREEN)✓ Migrations complete$(NC)"

db-reset:
	@echo "$(YELLOW)Resetting database...$(NC)"
	@docker-compose down -v
	@docker-compose up -d postgres
	@sleep 3
	@poetry run alembic upgrade head
	@echo "$(GREEN)✓ Database reset$(NC)"
