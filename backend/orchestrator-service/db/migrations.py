"""
db/migrations.py — Schema migration helpers.

Handles upgrading from the v1 schema (agent-service + search-service)
to the v2 schema (orchestrator-service).  All operations are additive
and idempotent — they never drop existing data.
"""

from __future__ import annotations

import logging
from .connection import get_pool

log = logging.getLogger("ars.db.migrations")


async def run_migrations() -> None:
    """
    Run all pending migrations.  Safe to call on every startup.

    Migrations are numbered and tracked in a `schema_version` table.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Ensure migration tracking table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                description TEXT
            );
        """)

        current = await conn.fetchval(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        )
        log.info("Current schema version: %d", current)

        for version, description, sql in _MIGRATIONS:
            if version > current:
                log.info("Applying migration %d: %s", version, description)
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_version (version, description) VALUES ($1, $2)",
                    version,
                    description,
                )
                log.info("Migration %d applied ✓", version)


# --------------------------------------------------------------------------
# Migration registry — append new migrations here.
# Format: (version, description, sql)
# --------------------------------------------------------------------------
_MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Add columns to legacy agent_memory if missing",
        """
        ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
        ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS outcome_type TEXT DEFAULT 'mixed';
        ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 0.5;
        ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS topic TEXT;
        ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS anti_pattern TEXT;
        """,
    ),
    (
        2,
        "Create paper_chunks embedding index if data exists",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_paper_chunks_embedding'
            ) THEN
                IF (SELECT COUNT(*) FROM paper_chunks) > 0 THEN
                    CREATE INDEX idx_paper_chunks_embedding
                        ON paper_chunks USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 20);
                END IF;
            END IF;
        END $$;
        """,
    ),
]
