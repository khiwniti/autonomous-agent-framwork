# Agent Platform — A2A Contract

Front door: `dev-agent` (FastAPI). Base URL = `AGENT_PLATFORM_URL`.

- `GET  /.well-known/agent.json` — agent card (skills, capabilities)
- `POST /tasks/send` — create task (non-streaming) → `{ id, session_id, status }`
- `POST /tasks/sendSubscribe` — create task with SSE stream of `{type,data}` events
  - `type: "log"`   → `{ messageEn, messageTh }`
  - `type: "artifact"` → a BuildPlan (vertical,title*,description*,summary*,mockEndpoint,files[],inputs[])
  - `type: "status"` → "completed" | "failed"
  - `type: "error"`  → string reason
- `GET  /health`, `GET /ready`

Auth: `Authorization: Bearer ${AGENT_PLATFORM_TOKEN}` (see AuthenticationMethod on the card).

Env: `DEV_AGENT_URL`, `MCP_URL`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `AGENT_PLATFORM_TOKEN`.
