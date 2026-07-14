"""
recovery/dead_letter.py — Dead letter queue for permanent failures.

Tasks/nodes that exhaust all retries land here for manual inspection
and optional re-execution.
"""

from __future__ import annotations

import logging
from db.connection import get_pool

log = logging.getLogger("ars.recovery.dlq")


class DeadLetterQueue:
    """Manage permanently failed tasks."""

    async def list_failed(self, limit: int = 50) -> list[dict]:
        """List entries in the dead letter queue."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, task_id, node_id, worker_name, error,
                       created_at, retried_at
                FROM dead_letter_queue
                WHERE retried_at IS NULL
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]

    async def mark_retried(self, dlq_id: int) -> None:
        """Mark a DLQ entry as retried."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE dead_letter_queue SET retried_at = NOW() WHERE id = $1",
                dlq_id,
            )
        log.info("DLQ entry %d marked as retried", dlq_id)
