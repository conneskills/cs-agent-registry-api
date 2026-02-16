"""Unit tests for Agent Registry API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app, startup, shutdown


@pytest_asyncio.fixture
async def client():
    """Create test client with initialized storage."""
    await startup()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await shutdown()


# ============================================================================
# HEALTH
# ============================================================================

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["storage"]["type"] == "memory"
    assert data["storage"]["status"] == "ok"


# ============================================================================
# SKILLS CRUD
# ============================================================================

@pytest.mark.asyncio
async def test_create_skill(client):
    payload = {"id": "s-1", "name": "Summarization", "description": "Summarize text", "tags": ["nlp"]}
    resp = await client.post("/skills", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"
    assert resp.json()["skill"]["id"] == "s-1"


@pytest.mark.asyncio
async def test_create_skill_duplicate(client):
    payload = {"id": "s-dup", "name": "Dup", "description": "Dup skill"}
    await client.post("/skills", json=payload)
    resp = await client.post("/skills", json=payload)
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_skill(client):
    payload = {"id": "s-get", "name": "Get Test", "description": "For get test"}
    await client.post("/skills", json=payload)
    resp = await client.get("/skills/s-get")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_get_skill_not_found(client):
    resp = await client.get("/skills/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_skills(client):
    await client.post("/skills", json={"id": "s-a", "name": "A", "description": "A"})
    await client.post("/skills", json={"id": "s-b", "name": "B", "description": "B"})
    resp = await client.get("/skills")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 2


@pytest.mark.asyncio
async def test_delete_skill(client):
    await client.post("/skills", json={"id": "s-del", "name": "Del", "description": "Del"})
    resp = await client.delete("/skills/s-del")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    # Verify it's gone
    resp = await client.get("/skills/s-del")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_skill_not_found(client):
    resp = await client.delete("/skills/nonexistent")
    assert resp.status_code == 404


# ============================================================================
# TOOLS CRUD
# ============================================================================

@pytest.mark.asyncio
async def test_create_tool(client):
    payload = {"id": "t-1", "name": "Web Search", "description": "Search the web", "provider": "builtin"}
    resp = await client.post("/tools", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"


@pytest.mark.asyncio
async def test_create_tool_duplicate(client):
    payload = {"id": "t-dup", "name": "Dup Tool", "description": "Dup"}
    await client.post("/tools", json=payload)
    resp = await client.post("/tools", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_tool(client):
    await client.post("/tools", json={"id": "t-get", "name": "Get Tool", "description": "Get"})
    resp = await client.get("/tools/t-get")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Tool"


@pytest.mark.asyncio
async def test_get_tool_not_found(client):
    resp = await client.get("/tools/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_tools(client):
    await client.post("/tools", json={"id": "t-a", "name": "A", "description": "A"})
    resp = await client.get("/tools")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


@pytest.mark.asyncio
async def test_delete_tool(client):
    await client.post("/tools", json={"id": "t-del", "name": "Del", "description": "Del"})
    resp = await client.delete("/tools/t-del")
    assert resp.status_code == 200
    resp = await client.get("/tools/t-del")
    assert resp.status_code == 404


# ============================================================================
# RAG CONFIG CRUD
# ============================================================================

@pytest.mark.asyncio
async def test_create_rag(client):
    payload = {"id": "r-1", "name": "My RAG", "rag_type": "vector_store", "top_k": 10}
    resp = await client.post("/rag", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"


@pytest.mark.asyncio
async def test_create_rag_duplicate(client):
    payload = {"id": "r-dup", "name": "Dup RAG", "rag_type": "web_search"}
    await client.post("/rag", json=payload)
    resp = await client.post("/rag", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_rag(client):
    await client.post("/rag", json={"id": "r-get", "name": "Get RAG", "rag_type": "document"})
    resp = await client.get("/rag/r-get")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get RAG"


@pytest.mark.asyncio
async def test_get_rag_not_found(client):
    resp = await client.get("/rag/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_rag(client):
    await client.post("/rag", json={"id": "r-del", "name": "Del RAG", "rag_type": "vector_store"})
    resp = await client.delete("/rag/r-del")
    assert resp.status_code == 200
    resp = await client.get("/rag/r-del")
    assert resp.status_code == 404


# ============================================================================
# AGENTS CRUD
# ============================================================================

@pytest.mark.asyncio
async def test_create_agent(client):
    payload = {
        "name": "Test Agent",
        "description": "A test agent",
        "url": "http://localhost:8000",
        "version": "1.0.0",
        "agent_type": "general",
        "tags": ["test"],
    }
    resp = await client.post("/agents", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert "agent_id" in data
    assert data["agent"]["name"] == "Test Agent"


@pytest.mark.asyncio
async def test_create_agent_with_skills(client):
    # Create a skill first
    await client.post("/skills", json={"id": "s-ref", "name": "Referenced Skill", "description": "Ref"})
    payload = {
        "name": "Skilled Agent",
        "description": "Agent with skills",
        "url": "http://localhost:8001",
        "skill_ids": ["s-ref"],
    }
    resp = await client.post("/agents", json=payload)
    assert resp.status_code == 200
    agent = resp.json()["agent"]
    assert len(agent["skills"]) == 1
    assert agent["skills"][0]["name"] == "Referenced Skill"


@pytest.mark.asyncio
async def test_create_agent_with_tools(client):
    await client.post("/tools", json={"id": "t-ref", "name": "Referenced Tool", "description": "Ref"})
    payload = {
        "name": "Tooled Agent",
        "description": "Agent with tools",
        "url": "http://localhost:8002",
        "tool_ids": ["t-ref"],
    }
    resp = await client.post("/agents", json=payload)
    assert resp.status_code == 200
    agent = resp.json()["agent"]
    assert len(agent["tools"]) == 1


@pytest.mark.asyncio
async def test_get_agent(client):
    resp = await client.post("/agents", json={"name": "Get Agent", "description": "Get", "url": "http://a"})
    agent_id = resp.json()["agent_id"]
    resp = await client.get(f"/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Agent"


@pytest.mark.asyncio
async def test_get_agent_not_found(client):
    resp = await client.get("/agents/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_agent(client):
    resp = await client.post("/agents", json={"name": "Original", "description": "V1", "url": "http://a"})
    agent_id = resp.json()["agent_id"]
    resp = await client.put(f"/agents/{agent_id}", json={"name": "Updated", "description": "V2", "url": "http://b"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"
    # Verify update
    resp = await client.get(f"/agents/{agent_id}")
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_update_agent_not_found(client):
    resp = await client.put("/agents/nonexistent", json={"name": "X", "description": "X", "url": "http://x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(client):
    resp = await client.post("/agents", json={"name": "Del Agent", "description": "Del", "url": "http://a"})
    agent_id = resp.json()["agent_id"]
    resp = await client.delete(f"/agents/{agent_id}")
    assert resp.status_code == 200
    resp = await client.get(f"/agents/{agent_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_not_found(client):
    resp = await client.delete("/agents/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_agents(client):
    await client.post("/agents", json={"name": "A1", "description": "A1", "url": "http://a", "tags": ["ml"]})
    resp = await client.get("/agents")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


@pytest.mark.asyncio
async def test_list_agents_filter_by_tag(client):
    await client.post("/agents", json={"name": "Tagged", "description": "Tagged", "url": "http://a", "tags": ["unique-tag"]})
    resp = await client.get("/agents?tag=unique-tag")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


@pytest.mark.asyncio
async def test_list_agents_filter_by_type(client):
    await client.post("/agents", json={"name": "Researcher", "description": "Research", "url": "http://a", "agent_type": "researcher"})
    resp = await client.get("/agents?agent_type=researcher")
    assert resp.status_code == 200
    assert all(a["agent_type"] == "researcher" for a in resp.json()["agents"])


@pytest.mark.asyncio
async def test_create_agent_with_runtime_config(client):
    payload = {
        "name": "Pipeline Agent",
        "description": "Sequential pipeline",
        "url": "http://localhost:8003",
        "execution_type": "sequential",
        "roles": [
            {"name": "researcher", "prompt_inline": "Research the topic"},
            {"name": "writer", "prompt_inline": "Write a summary"},
        ],
    }
    resp = await client.post("/agents", json=payload)
    assert resp.status_code == 200
    agent = resp.json()["agent"]
    assert agent["runtime_config"] is not None
    assert agent["runtime_config"]["execution_type"] == "sequential"
    assert len(agent["runtime_config"]["roles"]) == 2


@pytest.mark.asyncio
async def test_create_agent_without_url(client):
    """Agents can be created without url to break the circular dependency."""
    resp = await client.post("/agents", json={"name": "No URL Agent", "description": "Config first"})
    assert resp.status_code == 200
    agent_id = resp.json()["agent_id"]
    agent = resp.json()["agent"]
    assert agent["url"] == ""
    assert agent_id is not None


@pytest.mark.asyncio
async def test_patch_agent_url(client):
    """Two-phase flow: create config → deploy → patch URL."""
    # 1. Register config (no url)
    resp = await client.post("/agents", json={"name": "Deploy Me", "description": "Pending deploy"})
    agent_id = resp.json()["agent_id"]

    # 2. After deploy, set the URL
    resp = await client.patch(f"/agents/{agent_id}/url", json={"url": "https://my-agent-xyz.run.app"})
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://my-agent-xyz.run.app"

    # 3. Verify it persisted
    resp = await client.get(f"/agents/{agent_id}")
    assert resp.json()["url"] == "https://my-agent-xyz.run.app"


@pytest.mark.asyncio
async def test_patch_agent_url_not_found(client):
    resp = await client.patch("/agents/nonexistent/url", json={"url": "http://x"})
    assert resp.status_code == 404


# ============================================================================
# ARCHITECTURES CRUD
# ============================================================================

@pytest.mark.asyncio
async def test_create_architecture(client):
    payload = {
        "name": "Test Arch",
        "description": "A test architecture",
        "pattern": "sequential",
        "agents": [{"agent_id": "fake-id", "role": "worker"}],
    }
    resp = await client.post("/architectures", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert "architecture_id" in data


@pytest.mark.asyncio
async def test_get_architecture(client):
    resp = await client.post("/architectures", json={
        "name": "Get Arch", "description": "Get", "pattern": "parallel", "agents": []
    })
    arch_id = resp.json()["architecture_id"]
    resp = await client.get(f"/architectures/{arch_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Arch"


@pytest.mark.asyncio
async def test_get_architecture_not_found(client):
    resp = await client.get("/architectures/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_architectures(client):
    await client.post("/architectures", json={
        "name": "Arch A", "description": "A", "pattern": "sequential", "agents": []
    })
    resp = await client.get("/architectures")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


# ============================================================================
# DISCOVERY
# ============================================================================

@pytest.mark.asyncio
async def test_discover_no_match(client):
    resp = await client.get("/discover?query=something+random")
    assert resp.status_code == 200
    assert "message" in resp.json() or "recommended_agent" in resp.json()


@pytest.mark.asyncio
async def test_discover_with_matching_agent(client):
    # Create skill and agent with that skill
    await client.post("/skills", json={
        "id": "s-disc", "name": "Translation", "description": "Translate text between languages",
        "tags": ["translation", "language"], "examples": ["translate this to Spanish"]
    })
    await client.post("/agents", json={
        "name": "Translator", "description": "Translation agent", "url": "http://translator",
        "skill_ids": ["s-disc"], "is_public": True,
    })
    resp = await client.get("/discover?query=translate+to+Spanish")
    assert resp.status_code == 200
    data = resp.json()
    if "recommended_agent" in data:
        assert data["recommended_agent"]["name"] == "Translator"


# ============================================================================
# AUTH (when MASTER_KEY is set)
# ============================================================================

@pytest.mark.asyncio
async def test_auth_no_key_dev_mode(client):
    """Without MASTER_KEY set, all requests pass with 'dev' key."""
    resp = await client.get("/skills")
    assert resp.status_code == 200


# ============================================================================
# STORAGE (MemoryStorage unit tests)
# ============================================================================

@pytest.mark.asyncio
async def test_memory_storage_crud():
    from storage import MemoryStorage
    s = MemoryStorage()
    await s.init_db()

    # Put & get
    await s.put("skills", "k1", {"name": "Skill 1"})
    assert await s.get("skills", "k1") == {"name": "Skill 1"}
    assert await s.exists("skills", "k1") is True

    # List
    items = await s.list_all("skills")
    assert len(items) == 1

    # Delete
    assert await s.delete("skills", "k1") is True
    assert await s.get("skills", "k1") is None
    assert await s.delete("skills", "k1") is False

    # Health
    h = await s.health()
    assert h["type"] == "memory"
    assert h["status"] == "ok"
