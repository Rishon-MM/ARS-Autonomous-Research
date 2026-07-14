"""
observability/metrics.py — Execution metrics collection.

Provides a collector that aggregates worker and tool metrics
from the execution log for dashboarding.
"""

from __future__ import annotations

import logging
from db.connection import get_pool

log = logging.getLogger("ars.observability.metrics")


class MetricsCollector:
    """Query execution history for aggregate metrics."""

    async def get_task_metrics(self, task_id: str) -> dict:
        """Get aggregated metrics for a single task."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT worker_name,
                       COUNT(*) as executions,
                       SUM(duration_ms) as total_duration_ms,
                       SUM(tokens_used) as total_tokens,
                       SUM(retry_count) as total_retries,
                       COUNT(*) FILTER (WHERE status = 'completed') as successes,
                       COUNT(*) FILTER (WHERE status = 'failed') as failures
                FROM execution_history
                WHERE task_id = $1
                GROUP BY worker_name
                ORDER BY worker_name
                """,
                task_id,
            )

        workers = {}
        for r in rows:
            workers[r["worker_name"]] = {
                "executions": r["executions"],
                "total_duration_ms": r["total_duration_ms"],
                "total_tokens": r["total_tokens"],
                "total_retries": r["total_retries"],
                "successes": r["successes"],
                "failures": r["failures"],
            }

        return {
            "task_id": task_id,
            "workers": workers,
            "total_workers": len(workers),
        }

    async def get_system_metrics(self) -> dict:
        """Get system-wide aggregate metrics."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            total_tasks = await conn.fetchval("SELECT COUNT(*) FROM tasks")
            completed = await conn.fetchval(
                "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
            )
            failed = await conn.fetchval(
                "SELECT COUNT(*) FROM tasks WHERE status = 'failed'"
            )
            dlq_count = await conn.fetchval(
                "SELECT COUNT(*) FROM dead_letter_queue WHERE retried_at IS NULL"
            )
            avg_latency = await conn.fetchval(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))
                FROM tasks
                WHERE status = 'completed' AND started_at IS NOT NULL
                """
            )

        return {
            "total_tasks": total_tasks or 0,
            "completed": completed or 0,
            "failed": failed or 0,
            "dlq_pending": dlq_count or 0,
            "avg_latency_seconds": round(float(avg_latency or 0), 1),
        }
