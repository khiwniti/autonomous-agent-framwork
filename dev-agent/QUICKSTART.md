# Quick Start Guide

Get the Autonomous Development Agent running in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- Poetry (install: `curl -sSL https://install.python-poetry.org | python3 -`)
- LLM API access (OpenAI, Ollama, or custom OpenAI-compatible endpoint)

## Installation

```bash
# Navigate to project directory
cd autonomous-dev-agent

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set your LLM configuration:

**For OpenAI:**
```env
AGENT_LLM_PROVIDER=openai
AGENT_LLM_API_BASE_URL=https://api.openai.com/v1
AGENT_LLM_API_KEY=sk-your-api-key-here
AGENT_LLM_MODEL=gpt-4-turbo-preview
```

**For Ollama (local):**
```env
AGENT_LLM_PROVIDER=ollama
AGENT_LLM_API_BASE_URL=http://localhost:11434/v1
AGENT_LLM_API_KEY=ollama
AGENT_LLM_MODEL=llama2
```

**For Custom OpenAI-Compatible:**
```env
AGENT_LLM_PROVIDER=openai
AGENT_LLM_API_BASE_URL=https://your-api.example.com/v1
AGENT_LLM_API_KEY=your-api-key
AGENT_LLM_MODEL=your-model
```

## Usage

### Check Configuration

```bash
poetry run agent info
```

### Single Task Execution

```bash
poetry run agent run --task "Calculate 25 * 16 + 100"
```

### Interactive Mode

```bash
poetry run agent interactive
```

Then enter tasks interactively:
```
Task: Calculate the factorial of 5
Task: What is 2^10?
Task: exit
```

### Available Commands

```bash
# Run a single task
poetry run agent run --task "your task here"

# Interactive session
poetry run agent interactive

# Show configuration
poetry run agent info

# Validate config file
poetry run agent validate-config .env

# Show help
poetry run agent --help
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/agent --cov-report=html

# Run specific test file
poetry run pytest tests/integration/test_phase1.py

# Run verbose
poetry run pytest -v
```

## Phase 1 Capabilities

**Currently Available:**
- ✅ ReAct reasoning loop (plan → execute → reflect)
- ✅ OpenAI-compatible LLM integration
- ✅ Working memory system
- ✅ Tool framework with calculator example
- ✅ CLI interface (single task & interactive)
- ✅ Loop detection and safety limits
- ✅ Configurable via environment variables

**Coming in Phase 2:**
- File operations (read, write, search)
- Shell execution
- Git operations
- Browser automation (Playwright)
- Code analysis (tree-sitter)
- Docker sandbox isolation
- MCP server integration

## Troubleshooting

### Issue: `ModuleNotFoundError`

**Solution:** Ensure you're in Poetry shell:
```bash
poetry shell
```

### Issue: LLM API connection error

**Solution:** Verify your credentials:
```bash
# Check config
poetry run agent info

# Test with a simple task
poetry run agent run --task "Say hello"
```

### Issue: `No module named 'agent'`

**Solution:** Install in development mode:
```bash
poetry install
```

## Next Steps

1. **Add more tools**: See `src/agent/tools/calculator.py` for examples
2. **Customize prompts**: Edit templates in `src/agent/core/engine.py`
3. **Adjust limits**: Modify `max_iterations`, `reflection_interval` in `.env`
4. **Add SDLC agents**: Coming in Phase 4

## Examples

### Example 1: Simple Calculation

```bash
poetry run agent run --task "What is 15% of 250?"
```

Expected output:
```
✓ Success
Output: The calculation shows that 15% of 250 is 37.5
Iterations: 3
```

### Example 2: Complex Expression

```bash
poetry run agent run --task "Calculate (50 + 30) * 2 - 20"
```

## Development

```bash
# Format code
poetry run black src/ tests/

# Lint
poetry run ruff check src/ tests/ --fix

# Type check
poetry run mypy src/

# Run pre-commit hooks
poetry run pre-commit run --all-files
```

## Support

- **Issues**: Create an issue on GitHub
- **Documentation**: See `README.md` and `docs/`
- **Configuration**: All options in `.env.example`

---

**Status**: Phase 1 Complete ✅
**Next**: Phase 2 (Tool Ecosystem) starts next session
