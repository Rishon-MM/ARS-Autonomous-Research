"""
API Gateway — Routes all frontend requests to backend services.

Updated for the v2 graph-orchestrated architecture:
- All agent/research/search/knowledge routes → orchestrator-service
- Export routes → export-service (unchanged)
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import httpx
import os

app = FastAPI(title="API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Service URLs ──────────────────────────────────────────────────
# v2: orchestrator-service replaces agent-service + search-service
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-service:8001")
EXPORT_URL = os.getenv("EXPORT_SERVICE_URL", "http://export-service:8002")

# v1 backward compat (same target)
AGENT_URL = os.getenv("AGENT_SERVICE_URL", ORCHESTRATOR_URL)
SEARCH_URL = os.getenv("SEARCH_SERVICE_URL", ORCHESTRATOR_URL)

client = httpx.AsyncClient(timeout=300.0)


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API Gateway is running", "version": "2.0.0"}


async def async_generator(response):
    async for chunk in response.aiter_raw():
        yield chunk


# ── Core Research Endpoints (→ orchestrator) ──────────────────────

@app.post("/api/chat")
async def proxy_chat(request: Request):
    """Primary research endpoint — streams SSE events."""
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    body = await request.body()

    req = client.build_request(
        "POST",
        f"{ORCHESTRATOR_URL}/api/chat",
        headers=headers,
        content=body,
    )

    response = await client.send(req, stream=True)
    return StreamingResponse(
        async_generator(response),
        headers=dict(response.headers),
        status_code=response.status_code,
    )


@app.get("/api/settings")
async def proxy_settings():
    response = await client.get(f"{ORCHESTRATOR_URL}/api/settings")
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.get("/api/health/local_llama")
async def proxy_llama_health():
    response = await client.get(f"{ORCHESTRATOR_URL}/api/health/local_llama")
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


# ── Task Management Endpoints (→ orchestrator) ────────────────────

@app.post("/api/tasks")
async def proxy_create_task(request: Request):
    body = await request.body()
    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/tasks",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.get("/api/tasks/{task_id}")
async def proxy_get_task(task_id: str):
    response = await client.get(f"{ORCHESTRATOR_URL}/api/tasks/{task_id}")
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.get("/api/tasks/{task_id}/stream")
async def proxy_stream_task(task_id: str):
    req = client.build_request("GET", f"{ORCHESTRATOR_URL}/api/tasks/{task_id}/stream")
    response = await client.send(req, stream=True)
    return StreamingResponse(
        async_generator(response),
        headers=dict(response.headers),
        status_code=response.status_code,
    )


@app.post("/api/tasks/{task_id}/resume")
async def proxy_resume_task(task_id: str):
    req = client.build_request("POST", f"{ORCHESTRATOR_URL}/api/tasks/{task_id}/resume")
    response = await client.send(req, stream=True)
    return StreamingResponse(
        async_generator(response),
        headers=dict(response.headers),
        status_code=response.status_code,
    )


@app.get("/api/tasks")
async def proxy_list_tasks(request: Request):
    params = dict(request.query_params)
    response = await client.get(f"{ORCHESTRATOR_URL}/api/tasks", params=params)
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.get("/api/tasks/{task_id}/evaluation")
async def proxy_evaluation(task_id: str):
    response = await client.get(f"{ORCHESTRATOR_URL}/api/tasks/{task_id}/evaluation")
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.get("/api/metrics")
async def proxy_metrics():
    response = await client.get(f"{ORCHESTRATOR_URL}/api/metrics")
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


# ── Export (→ export-service) ─────────────────────────────────────

@app.post("/api/export")
async def proxy_export(request: Request):
    body = await request.body()
    # Try orchestrator first (has built-in export), fall back to export-service
    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/export",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


# ── Knowledge & Papers (→ orchestrator) ───────────────────────────

@app.get("/api/papers/search")
async def proxy_search(request: Request, q: str):
    headers = dict(request.headers)
    headers.pop("host", None)

    req = client.build_request(
        "GET",
        f"{ORCHESTRATOR_URL}/api/papers/search",
        params={"q": q},
        headers=headers,
    )

    response = await client.send(req, stream=True)
    return StreamingResponse(
        async_generator(response),
        headers=dict(response.headers),
        status_code=response.status_code,
    )


@app.post("/api/papers/analyze")
async def proxy_analyze(request: Request):
    body = await request.body()
    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/papers/analyze",
        content=body,
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.post("/api/knowledge/crawl")
async def proxy_crawl(request: Request):
    body = await request.body()
    req = client.build_request(
        "POST",
        f"{ORCHESTRATOR_URL}/api/knowledge/crawl",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    response = await client.send(req, stream=True)
    return StreamingResponse(
        async_generator(response),
        headers=dict(response.headers),
        status_code=response.status_code,
    )


@app.get("/api/knowledge/stats")
async def proxy_knowledge_stats():
    response = await client.get(f"{ORCHESTRATOR_URL}/api/knowledge/stats", timeout=10.0)
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))


@app.post("/api/rag/query")
async def proxy_rag_query(request: Request):
    body = await request.body()
    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/rag/query",
        content=body,
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )
    return Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))
