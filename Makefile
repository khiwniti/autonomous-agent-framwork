.PHONY: help install start stop status logs

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)=== Autonomous Agent Framework - Dev Makefile ===$(NC)"
	@echo "Available commands:"
	@echo "  $(GREEN)make install$(NC)  - Install dependencies for Orchestrator and Dev Agent"
	@echo "  $(GREEN)make start$(NC)    - Start Dev Agent (A2A & MCP) and Orchestrator"
	@echo "  $(GREEN)make stop$(NC)     - Stop all running agent services"
	@echo "  $(GREEN)make status$(NC)   - Check status of all services"

install:
	@echo "$(YELLOW)Installing Orchestrator (Google ADK) dependencies...$(NC)"
	cd orchestrator && uv sync
	@echo "$(YELLOW)Installing Dev Agent (LangGraph/A2A) dependencies...$(NC)"
	cd dev-agent && poetry install

start:
	@echo "$(YELLOW)Starting Autonomous Dev Agent (A2A & MCP Sandbox)...$(NC)"
	cd dev-agent && docker compose build agent-api && docker compose up -d
	@echo "$(YELLOW)Starting Google ADK Orchestrator...$(NC)"
	cd orchestrator && uvx google-agents-cli run --start-server "Ping" > orchestrator.log 2>&1 &
	@echo "$(GREEN)All agent services started!$(NC)"
	@echo "Orchestrator: http://localhost:8000"
	@echo "Dev Agent A2A: http://localhost:8001"
	@echo "Sandbox MCP: http://localhost:8002"

stop:
	@echo "$(YELLOW)Stopping Orchestrator...$(NC)"
	-cd orchestrator && uvx google-agents-cli run --stop-server
	@echo "$(YELLOW)Stopping Dev Agent...$(NC)"
	-cd dev-agent && docker compose down
	@echo "$(GREEN)All agent services stopped.$(NC)"

status:
	@echo "$(BLUE)--- Service Status ---$(NC)"
	@echo "$(YELLOW)Orchestrator (port 8000):$(NC) \`lsof -i :8000 >/dev/null && echo '$(GREEN)Running$(NC)' || echo 'Stopped'\`"
	@echo "$(YELLOW)A2A Server (port 8001):$(NC) \`lsof -i :8001 >/dev/null && echo '$(GREEN)Running$(NC)' || echo 'Stopped'\`"
	@echo "$(YELLOW)Sandbox MCP (port 8002):$(NC) \`lsof -i :8002 >/dev/null && echo '$(GREEN)Running$(NC)' || echo 'Stopped'\`"
