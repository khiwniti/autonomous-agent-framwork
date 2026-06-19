# Autonomous Agent Framework

This repository houses the extracted Google AI Agent Framework. It consists of two main Python components:

1. **`orchestrator/`** (formerly `mvp-ai-agent`): Orchestrator using the Google Agent Development Kit (ADK) and Gemini/Vertex AI.
2. **`dev-agent/`** (formerly `autonomous-dev-agent`): Autonomous Dev Agent exposing a LangGraph workflow behind an A2A HTTP server with an MCP sandbox interface.

## Getting Started

Refer to the Makefile for common development tasks.

```bash
# Install dependencies
make install

# Start development services
make start

# Stop services
make stop
```

For API/Protocol contract details, see [CONTRACT.md](CONTRACT.md).
