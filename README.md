# cs-agent-registry-api

Agent Registry API — central configuration store for dynamic agent services.

## What It Does

Provides CRUD endpoints for:

| Entity | Endpoint | Description |
|--------|----------|-------------|
| **Agents** | `/agents` | Agent cards with runtime config (execution type, roles) |
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
  Create agent ────>│  GET  /agents/{id}   │<──── Agent containers read
  config via API    │  PATCH /agents/{id}/ │      config at startup
                    │        url           │
                    └──────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  cs-agent-service  │──── Prompts from LiteLLM
                    │  (N containers)    │     (GET /prompts/{ref}/info)
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
# List all agents
curl http://localhost:9500/agents

# Health check
curl http://localhost:9500/health
```

## Prompts

Prompts are managed in **LiteLLM**, not in the registry. The registry only stores agent config with `prompt_ref` or `prompt_inline` — the actual prompt resolution happens at runtime in `cs-agent-service`.

### Option A: Inline prompt (simplest)

Put the prompt directly in the role config. No external dependencies.

```bash
curl -X POST http://localhost:9500/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Agent",
    "description": "Simple agent with inline prompt",
    "execution_type": "single",
    "roles": [
      {
        "name": "researcher",
        "prompt_inline": "You are a research agent. Find accurate information.",
        "tools": ["Bash", "Read", "WebSearch"]
      }
    ]
  }'
```

### Option B: Prompt reference via LiteLLM

Create the prompt directly in LiteLLM, then reference it by name in the agent role.

```bash
# 1. Create prompt in LiteLLM (dotprompt format)
curl -X POST https://litellm.example.com/prompts \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_id": "agent-researcher",
    "litellm_params": {
      "prompt_integration": "dotprompt",
      "dotprompt_content": "---\nname: agent-researcher\n---\nYou are a research agent specialized in {domain}."
    }
  }'

# 2. Reference it in the agent role
curl -X POST http://localhost:9500/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Pipeline",
    "description": "Sequential pipeline",
    "execution_type": "sequential",
    "roles": [
      {"name": "researcher", "prompt_ref": "agent-researcher", "tools": ["Bash", "Read"]},
      {"name": "analyzer", "prompt_inline": "Analyze the research results.", "tools": ["Bash", "Read"]}
    ]
  }'
```

### How cs-agent-service resolves prompts at runtime

```
1. prompt_inline  → use directly (no network call)
2. prompt_ref     → LiteLLM (GET /prompts/{name}/info)
3. local file     → /app/prompts/{role}.txt
4. default        → "You are a {role} agent."
```

The registry is not involved in prompt resolution. LiteLLM owns prompts.

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

## Architecture (Production — Zero Cost)

All components scale to zero. No cost when idle.

```
┌──────────────────────┐       ┌──────────────────┐
│  cs-agent-registry   │──────>│  Neon Postgres   │
│  Cloud Run :9500     │       │  (serverless)    │
│  min-instances: 0    │       │  free: 0.5 GB    │
│  256Mi / 1 vCPU      │       └──────────────────┘
└──────────────────────┘
         │
         ├── cs-agent-service (:9100) reads config at startup
         └── LiteLLM registers public agents
```

| Component | Cost when idle | Free tier |
|---|---|---|
| Cloud Run | $0 (scale to zero) | 2M requests/month |
| Neon Postgres | $0 (scale to zero) | 0.5 GB storage |
| Artifact Registry | ~$0.10/GB/month | 0.5 GB free |
| Secret Manager | $0 | 6 active versions free |
| Cloud Build | $0 | 120 min/day free |

## Storage

| Mode | Config | Description |
|------|--------|-------------|
| **Memory** | _(default, dev only)_ | In-memory, data lost on restart |
| **Neon Postgres** | `DATABASE_URL=postgresql+asyncpg://...?sslmode=require` | **Production**, serverless, scale to zero |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | _(none)_ | Neon Postgres connection (**required in production**) |
| `LITELLM_URL` | `http://litellm:4000` | LiteLLM endpoint for agent registration |
| `LITELLM_MASTER_KEY` | _(none)_ | LiteLLM master key (Secret Manager) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(none)_ | Phoenix/OTLP tracing (optional, see below) |

## Deployment

Deployed to Cloud Run via Cloud Build. Secrets from GCP Secret Manager.

```bash
# 1. Create Neon project at https://neon.tech (free tier)
#    Copy connection string: postgresql+asyncpg://user:pass@ep-xxx.neon.tech/registry?sslmode=require

# 2. Store secrets in GCP Secret Manager
gcloud secrets create registry-database-url --data-file=-  # paste Neon URL
gcloud secrets create litellm-master-key --data-file=-      # paste key

# 3. Build + deploy
gcloud builds submit --config cloudbuild.yaml
```

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
