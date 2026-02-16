# cs-agent-registry-api

Agent Registry API — central configuration store for dynamic agent services.

## What It Does

Provides CRUD endpoints for:

| Entity | Endpoint | Description |
|--------|----------|-------------|
| **Agents** | `/agents` | Agent cards with runtime config (execution type, roles, prompts) |
| **Prompts** | `/prompts` | Reusable prompt templates with variables |
| **Skills** | `/skills` | Skill definitions for agent discovery |
| **Tools** | `/tools` | Tool definitions (MCP, OpenAPI, custom) |
| **RAG** | `/rag` | RAG configurations (vector stores, web search, etc.) |
| **Architectures** | `/architectures` | Multi-agent architecture definitions |
| **Discovery** | `/discover?query=...` | Skill-based agent matching |

## How It Fits

```
                    cs-agent-registry-api (:9500)
                    ┌──────────────────────┐
                    │  POST /agents        │
  Create agent ────>│  POST /prompts       │
  config via API    │  GET  /agents/{id}   │<──── Agent containers read
                    └──────────────────────┘      config at startup
                              │
                    ┌─────────┴─────────┐
                    │  cs-agent-service  │
                    │  (N containers)    │
                    │  AGENT_ID=xxx      │
                    └───────────────────-┘
```

Agent containers (from `conneskills/cs-agent-service`) call `GET /agents/{id}` at startup to load their runtime config.

## Quick Start

```bash
# Run locally
pip install fastapi uvicorn aiohttp httpx pydantic
uvicorn main:app --port 9500 --reload

# Or with Docker
docker build -t registry-api .
docker run -p 9500:9500 registry-api
```

## API Examples

```bash
# Create a prompt
curl -X POST http://localhost:9500/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "researcher",
    "template": "You are a research agent specialized in {domain}. Find accurate information.",
    "variables": ["domain"],
    "tags": ["research"]
  }'

# Create a dynamic agent (sequential pipeline)
curl -X POST http://localhost:9500/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Pipeline",
    "description": "Sequential: researcher → analyzer",
    "url": "",
    "execution_type": "sequential",
    "roles": [
      {"name": "researcher", "prompt_ref": "<prompt-id>", "tools": ["Bash","Read","WebSearch"]},
      {"name": "analyzer", "prompt_inline": "Analyze the research results.", "tools": ["Bash","Read"]}
    ]
  }'

# List all agents
curl http://localhost:9500/agents

# Health check
curl http://localhost:9500/health
```

## Storage

| Mode | Config | Description |
|------|--------|-------------|
| **Memory** | _(default)_ | In-memory, data lost on restart |
| **PostgreSQL** | `DATABASE_URL=postgresql+asyncpg://...` | Persistent, uses `registry` schema |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | _(none)_ | PostgreSQL connection (enables persistence) |
| `LITELLM_URL` | `http://litellm:4000` | LiteLLM endpoint for agent registration |
| `LITELLM_MASTER_KEY` | _(none)_ | LiteLLM master key |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(none)_ | Phoenix/OTLP tracing (optional, see below) |

## Observability (Optional)

Tracing is **fully optional**. If `OTEL_EXPORTER_OTLP_ENDPOINT` is not set or Phoenix is unreachable, the service uses a no-op tracer and runs normally without any errors.

```bash
# Without tracing (default)
uvicorn main:app --port 9500

# With Phoenix tracing
OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:4317 uvicorn main:app --port 9500
```

When using `docker-compose`, Phoenix is behind the `observability` profile:

```bash
# Without Phoenix
docker compose up litellm postgres redis registry-api

# With Phoenix
docker compose --profile observability up
```

The `tracing.py` module handles all degradation gracefully:
- No `OTEL_EXPORTER_OTLP_ENDPOINT` set → no-op tracer
- OpenTelemetry packages not installed → no-op tracer
- Phoenix unreachable at runtime → no-op tracer (no crash)

## Project Structure

```
cs-agent-registry-api/
├── Dockerfile
├── main.py              # FastAPI app with all endpoints
├── storage.py           # Storage backends (memory + PostgreSQL)
├── tracing.py           # Optional OTEL tracing (graceful no-op)
└── models/
    └── capabilities.py  # Data models: AgentCard, RuntimeConfig, etc.
```
