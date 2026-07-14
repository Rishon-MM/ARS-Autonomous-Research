"""
recovery/checkpoint.py — Checkpoint management.

Wraps the StateManager checkpoint methods with additional logic
for listing, pruning, and validating checkpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime

from state.state_manager import StateManager
from models.task_state import TaskState, TaskStatus

log = logging.getLogger("ars.recovery.checkpoint")


class CheckpointManager:
    """High-level checkpoint operations."""

    def __init__(self, state_manager: StateManager):
        self.sm = state_manager

    async def save(self, state: TaskState, node_id: str) -> str:
        """Save a checkpoint and return the checkpoint ID."""
        await self.sm.checkpoint(state, node_id)
        log.info("Checkpoint saved: task=%s node=%s", state.task_id, node_id)
        return f"{state.task_id}:{node_id}:{state.version}"

    async def restore(self, task_id: str) -> TaskState:
        """Restore from the latest checkpoint."""
        state = await self.sm.restore_from_checkpoint(task_id)
        state.status = TaskStatus.RESUMING
        log.info("Checkpoint restored: task=%s version=%d", task_id, state.version)
        return state

    async def list_checkpoints(self, task_id: str) -> list[dict]:
        """List all checkpoints for a task."""
        from db.connection import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, node_id, state_version, created_at
                FROM checkpoints
                WHERE task_id = $1
                ORDER BY created_at DESC
                """,
                task_id,
            )
        return [dict(r) for r in rows]
