# ARS — Autonomous Research System (Backend)

Graph-orchestrated research platform with centralized state management,
evidence-first verification, and quantitative evaluation.

## Architecture

```
backend/
├── api-gateway/            # HTTP proxy — routes frontend to orchestrator
├── orchestrator-service/   # Core — graph engine, workers, tools, knowledge
├── export-service/         # DOCX/PDF report export
└── docker-compose.yml      # Full stack: postgres, jaeger, services
```

## Quick Start

```bash
docker compose up --build
```

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8000 | Frontend-facing proxy |
| Orchestrator | 8001 | Graph engine, workers, knowledge |
| Export | 8002 | Report export (DOCX/PDF) |
| PostgreSQL | 5432 | State, knowledge base (pgvector) |
| Jaeger UI | 16686 | Distributed tracing |

## Environment Variables

Copy `.env.example` to `.env` and set:

```
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key        # optional
LOCAL_LLAMA_MODEL=your_model   # optional — for local llama.cpp
```

## Orchestrator Service

The core service is `orchestrator-service/` — a graph-based execution engine:

- **Graph Engine** (`graph/`) — DAG scheduling with parallel execution
- **Workers** (`workers/`) — Planner → N×Researcher → Verification → Writer → Reflection
- **Tools** (`tools/`) — 8 stateless tools (LLM, RAG retrieval, browser, ingestion, citation, memory)
- **Knowledge** (`knowledge/`) — Autonomous arXiv crawler (independent of reports)
- **State** (`state/`) — PostgreSQL-backed TaskState with optimistic locking
- **Recovery** (`recovery/`) — Checkpointing, retry with backoff, dead letter queue
- **Evaluation** (`evaluation/`) — Quantitative metrics per task
- **Observability** (`observability/`) — OpenTelemetry → Jaeger, structured JSON logging

## API Endpoints

### Research
- `POST /api/chat` — Create and stream a research task (SSE)
- `POST /api/tasks` — Create a task (async)
- `GET  /api/tasks/{id}` — Get task state
- `GET  /api/tasks/{id}/stream` — Stream task execution
- `POST /api/tasks/{id}/resume` — Resume from checkpoint

### Knowledge
- `POST /api/knowledge/crawl` — Trigger paper crawl
- `GET  /api/knowledge/stats` — Knowledge base stats
- `GET  /api/papers/search?q=...` — Search papers

### System
- `GET  /api/settings` — Available LLM providers
- `GET  /api/metrics` — System-wide metrics
- `POST /api/export` — Export report to DOCX/PDF
