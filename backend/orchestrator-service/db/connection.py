"""
db/connection.py — asyncpg connection pool management.

Provides a singleton pool used by the StateManager, tools, and
knowledge layer. Initializes the schema on first connect.
"""

from __future__ import annotations

import os
import asyncpg
import logging

log = logging.getLogger("ars.db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ars_user:ars_password@postgres:5432/ars_memory",
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return (and lazily create) the global asyncpg connection pool."""
    global _pool
    if _pool is None:
        log.info("Creating database connection pool → %s", DATABASE_URL)
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool (called on app shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("Database connection pool closed")


async def init_schema() -> None:
    """
    Create all required tables and extensions if they don't exist.

    This is idempotent — safe to call on every startup.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Read and execute the schema file
        import pathlib

        schema_path = pathlib.Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")

        await conn.execute(schema_sql)
        log.info("Database schema initialized")
