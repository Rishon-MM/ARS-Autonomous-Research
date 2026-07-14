"""
state/state_manager.py — Centralized TaskState persistence.

All state mutations flow through this manager.  It handles:
- CRUD operations on TaskState
- Optimistic locking via version numbers
- Checkpoint creation and restoration
- Serialization to/from PostgreSQL JSONB
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from models.task_state import TaskState, TaskStatus
from db.connection import get_pool

log = logging.getLogger("ars.state")


class StateManager:
    """
    Persistent state manager backed by PostgreSQL.

    Every save increments the version counter.  Concurrent writes
    on the same version are rejected (optimistic locking).
    """

    # ── Create ────────────────────────────────────────────────────

    async def create_task(
        self,
        query: str,
        provider: str = "gemini",
        agent_providers: dict[str, str] | None = None,
        agent_temperatures: dict[str, float] | None = None,
        library_only: bool = False,
        library_papers: list[dict] | None = None,
    ) -> TaskState:
        """Create a new task and persist it."""
        state = TaskState(
            query=query,
            provider=provider,
            agent_providers=agent_providers or {},
            agent_temperatures=agent_temperatures or {},
            library_only=library_only,
            library_papers=library_papers or [],
        )

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (id, query, status, version, provider, state, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                state.task_id,
                state.query,
                state.status.value,
                state.version,
                state.provider,
                state.model_dump_json(),
                state.created_at,
                state.updated_at,
            )

        log.info("Task created: %s (query=%r)", state.task_id, query[:80])
        return state

    # ── Read ──────────────────────────────────────────────────────

    async def load_task(self, task_id: str) -> TaskState:
        """Load a task by ID.  Raises ValueError if not found."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state FROM tasks WHERE id = $1", task_id
            )

        if not row:
            raise ValueError(f"Task not found: {task_id}")

        return TaskState.model_validate_json(row["state"])

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return summary list of tasks."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT id, query, status, version, created_at, updated_at,
                           started_at, completed_at
                    FROM tasks
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    status.value,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, query, status, version, created_at, updated_at,
                           started_at, completed_at
                    FROM tasks
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
        return [dict(r) for r in rows]

    # ── Update ────────────────────────────────────────────────────

    async def save_task(self, state: TaskState) -> None:
        """
        Persist the task state.  Increments version and uses
        optimistic locking to prevent lost updates.
        """
        old_version = state.version
        state.bump_version()

        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tasks
                SET query = $1,
                    status = $2,
                    version = $3,
                    provider = $4,
                    state = $5,
                    updated_at = $6,
                    started_at = $7,
                    completed_at = $8
                WHERE id = $9 AND version = $10
                """,
                state.query,
                state.status.value,
                state.version,
                state.provider,
                state.model_dump_json(),
                state.updated_at,
                state.started_at,
                state.completed_at,
                state.task_id,
                old_version,
            )

        if result == "UPDATE 0":
            raise RuntimeError(
                f"Optimistic lock conflict on task {state.task_id}: "
                f"expected version {old_version}, but row was already updated"
            )

        log.debug(
            "Task saved: %s v%d → v%d (status=%s)",
            state.task_id,
            old_version,
            state.version,
            state.status.value,
        )

    # ── Checkpoints ───────────────────────────────────────────────

    async def checkpoint(self, state: TaskState, node_id: str) -> None:
        """Save a checkpoint after a node completes successfully."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO checkpoints (task_id, node_id, state_version, state_snapshot)
                VALUES ($1, $2, $3, $4)
                """,
                state.task_id,
                node_id,
                state.version,
                state.model_dump_json(),
            )
        log.info(
            "Checkpoint saved: task=%s node=%s version=%d",
            state.task_id,
            node_id,
            state.version,
        )

    async def restore_from_checkpoint(self, task_id: str) -> TaskState:
        """Restore the latest checkpoint for a task."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT state_snapshot FROM checkpoints
                WHERE task_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                task_id,
            )

        if not row:
            raise ValueError(f"No checkpoints found for task: {task_id}")

        state = TaskState.model_validate_json(row["state_snapshot"])
        state.status = TaskStatus.RESUMING
        log.info("Restored checkpoint: task=%s version=%d", task_id, state.version)
        return state

    # ── Execution History ─────────────────────────────────────────

    async def record_execution(
        self,
        task_id: str,
        node_id: str,
        worker_name: str,
        status: str,
        started_at: datetime,
        completed_at: datetime | None = None,
        duration_ms: int = 0,
        tokens_used: int = 0,
        tool_calls: list[dict] | None = None,
        error: str | None = None,
        retry_count: int = 0,
        metadata: dict | None = None,
    ) -> None:
        """Record a node execution in the history table."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO execution_history
                    (task_id, node_id, worker_name, status, started_at,
                     completed_at, duration_ms, tokens_used, tool_calls,
                     error, retry_count, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                task_id,
                node_id,
                worker_name,
                status,
                started_at,
                completed_at,
                duration_ms,
                tokens_used,
                json.dumps(tool_calls or []),
                error,
                retry_count,
                json.dumps(metadata or {}),
            )

    # ── Dead Letter Queue ─────────────────────────────────────────

    async def enqueue_dead_letter(
        self,
        task_id: str,
        node_id: str,
        worker_name: str,
        error: str,
        state: TaskState,
    ) -> None:
        """Send a permanently failed node to the dead letter queue."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO dead_letter_queue
                    (task_id, node_id, worker_name, error, state_snapshot)
                VALUES ($1, $2, $3, $4, $5)
                """,
                task_id,
                node_id,
                worker_name,
                error,
                state.model_dump_json(),
            )
        log.warning(
            "Dead letter: task=%s node=%s error=%s",
            task_id,
            node_id,
            error[:200],
        )

    # ── Evaluations ───────────────────────────────────────────────

    async def save_evaluation(self, task_id: str, metrics: dict) -> None:
        """Store evaluation metrics for a completed task."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO evaluations (task_id, metrics) VALUES ($1, $2)",
                task_id,
                json.dumps(metrics),
            )

    # ── Reflections ───────────────────────────────────────────────

    async def save_reflection(
        self,
        task_id: str,
        query: str,
        reflection: dict,
        embedding: list[float] | None = None,
    ) -> None:
        """Store a structured reflection record."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reflections
                    (task_id, query, outcome_type, confidence,
                     successful_strategies, failed_strategies,
                     retrieval_quality, verification_outcomes,
                     planning_feedback, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                task_id,
                query,
                reflection.get("outcome_type", "mixed"),
                reflection.get("confidence", 0.5),
                json.dumps(reflection.get("successful_strategies", [])),
                json.dumps(reflection.get("failed_strategies", [])),
                json.dumps(reflection.get("retrieval_quality", {})),
                json.dumps(reflection.get("verification_outcomes", {})),
                reflection.get("planning_feedback", ""),
                str(embedding) if embedding else None,
            )
