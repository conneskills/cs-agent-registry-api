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

## Skills, Tools & RAGs Injection

Agents don't define their capabilities inline. Instead, you create **skills**, **tools**, and **RAG configs** as independent resources, then reference them by ID when creating an agent.

### Step 1: Create resources

```bash
# Create a skill
curl -X POST http://localhost:9500/skills \
  -H "Content-Type: application/json" \
  -d '{
    "id": "s-translate",
    "name": "Translation",
    "description": "Translate text between languages",
    "tags": ["translation", "language"],
    "examples": ["translate this to Spanish", "convert to French"]
  }'

# Create a tool
curl -X POST http://localhost:9500/tools \
  -H "Content-Type: application/json" \
  -d '{
    "id": "t-websearch",
    "name": "Web Search",
    "description": "Search the web for information",
    "provider": "mcp",
    "mcp_server": "brave-search",
    "mcp_tool_name": "search"
  }'

# Create a RAG config
curl -X POST http://localhost:9500/rag \
  -H "Content-Type: application/json" \
  -d '{
    "id": "r-docs",
    "name": "Documentation KB",
    "rag_type": "vector_store",
    "vector_store_provider": "pgvector",
    "embedding_model": "text-embedding-ada-002",
    "top_k": 5
  }'
```

### Step 2: Inject into an agent

Reference the resource IDs via `skill_ids`, `tool_ids`, and `rag_ids`:

```bash
curl -X POST http://localhost:9500/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Agent",
    "description": "Researches and translates content",
    "url": "http://my-agent:8000",
    "skill_ids": ["s-translate"],
    "tool_ids": ["t-websearch"],
    "rag_ids": ["r-docs"],
    "tags": ["research"]
  }'
```

The API resolves each ID from storage and embeds the full resource data into the `CompleteAgentCard`. The resulting agent contains complete copies of each skill, tool, and RAG config — not just the IDs.

### How resolution works

```
POST /agents { skill_ids: ["s-translate"], tool_ids: ["t-websearch"], rag_ids: ["r-docs"] }
       │
       ▼
  storage.get("skills", "s-translate")    → SkillDefinition
  storage.get("tools", "t-websearch")     → ToolDefinition
  storage.get("rag_configs", "r-docs")    → RAGConfig
       │
       ▼
  CompleteAgentCard (stored with full embedded data)
```

> **Note:** Data is denormalized at creation time. If you update a skill after it's been injected into an agent, the agent keeps the old copy. To pick up changes, update the agent with `PUT /agents/{id}` using the same `skill_ids`.

### Discovery

The `/discover` endpoint uses skills to match agents to natural language queries:

```bash
curl "http://localhost:9500/discover?query=translate+this+to+Spanish"
```

The `SkillMatcher` scores each agent's skills against the query by checking skill names, descriptions, tags, and examples. The agent with the highest-scoring skills is returned.

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
