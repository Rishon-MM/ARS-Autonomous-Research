-- ==========================================================================
-- ARS Orchestrator — Database Schema
-- ==========================================================================
-- PostgreSQL + pgvector
-- All CREATE statements are idempotent (IF NOT EXISTS).
-- ==========================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

-- ─── Core Task State ─────────────────────────────────────────────────────
-- Stores the full serialized TaskState as JSONB alongside indexed columns
-- for fast querying.  Optimistic locking via `version`.
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    query           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    version         INTEGER NOT NULL DEFAULT 0,
    provider        TEXT NOT NULL DEFAULT 'gemini',
    state           JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks (created_at DESC);

-- ─── Execution History ───────────────────────────────────────────────────
-- One row per node execution (including retries).
CREATE TABLE IF NOT EXISTS execution_history (
    id              SERIAL PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    node_id         TEXT NOT NULL,
    worker_name     TEXT NOT NULL,
    status          TEXT NOT NULL,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER DEFAULT 0,
    tokens_used     INTEGER DEFAULT 0,
    tool_calls      JSONB DEFAULT '[]',
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_exec_hist_task ON execution_history (task_id);

-- ─── Checkpoints ─────────────────────────────────────────────────────────
-- Snapshot of TaskState at a specific graph node.  Used for crash recovery.
CREATE TABLE IF NOT EXISTS checkpoints (
    id              SERIAL PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    node_id         TEXT NOT NULL,
    state_version   INTEGER NOT NULL,
    state_snapshot  JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_task ON checkpoints (task_id, created_at DESC);

-- ─── Evaluations ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evaluations (
    id              SERIAL PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    metrics         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Dead Letter Queue ───────────────────────────────────────────────────
-- Permanently failed nodes/tasks land here for manual inspection.
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id              SERIAL PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    node_id         TEXT NOT NULL,
    worker_name     TEXT NOT NULL DEFAULT '',
    error           TEXT NOT NULL,
    state_snapshot  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retried_at      TIMESTAMPTZ
);

-- ─── Reflections (Self-Learning) ─────────────────────────────────────────
-- Replaces the old agent_memory table for new tasks.
-- Old agent_memory is preserved for backward compatibility.
CREATE TABLE IF NOT EXISTS reflections (
    id                      SERIAL PRIMARY KEY,
    task_id                 TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    query                   TEXT NOT NULL,
    outcome_type            TEXT NOT NULL DEFAULT 'mixed',
    confidence              FLOAT NOT NULL DEFAULT 0.5,
    successful_strategies   JSONB DEFAULT '[]',
    failed_strategies       JSONB DEFAULT '[]',
    retrieval_quality       JSONB DEFAULT '{}',
    verification_outcomes   JSONB DEFAULT '{}',
    planning_feedback       TEXT DEFAULT '',
    embedding               vector(384),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reflections_task ON reflections (task_id);

-- ─── Knowledge Base (paper chunks) ───────────────────────────────────────
-- Preserved from the original schema.  Only added IF NOT EXISTS guards.
CREATE TABLE IF NOT EXISTS paper_chunks (
    id              SERIAL PRIMARY KEY,
    paper_id        TEXT,
    title           TEXT,
    chunk           TEXT,
    embedding       vector(384)
);

-- IVFFlat index for fast cosine similarity search.
-- Can only be created if the table has rows; CREATE INDEX IF NOT EXISTS
-- will skip if already present.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_paper_chunks_embedding'
    ) THEN
        -- Only create the IVFFlat index if we have data (requires > 0 rows for lists param).
        -- For an empty table, fall back to no index — it will be created by migrations
        -- once data is loaded.
        IF (SELECT COUNT(*) FROM paper_chunks) > 0 THEN
            CREATE INDEX idx_paper_chunks_embedding
                ON paper_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 20);
        END IF;
    END IF;
END
$$;

-- ─── Legacy Agent Memory (preserved) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_memory (
    id              SERIAL PRIMARY KEY,
    query           TEXT,
    action          TEXT,
    result_summary  TEXT,
    lesson          TEXT,
    outcome_type    TEXT DEFAULT 'mixed',
    confidence      FLOAT DEFAULT 0.5,
    topic           TEXT,
    anti_pattern    TEXT,
    embedding       vector(384),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
