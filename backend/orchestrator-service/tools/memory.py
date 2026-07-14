"""
tools/memory.py — Self-learning memory tool.

Stores and retrieves lessons from past research sessions
using vector similarity search in pgvector.
"""

from __future__ import annotations

import json
import logging

from .base import BaseTool, ToolResult
from .retrieval import generate_embedding
from db.connection import get_pool

log = logging.getLogger("ars.tools.memory")


class StoreMemoryTool(BaseTool):
    """Store a research experience/lesson in the memory database."""

    @property
    def name(self) -> str:
        return "store_memory"

    @property
    def description(self) -> str:
        return "Store a research lesson (success or failure) for future reference."

    async def execute(
        self,
        query: str = "",
        lesson: str = "",
        outcome_type: str = "mixed",
        confidence: float = 0.5,
        anti_pattern: str = "",
        action: str = "research_task",
        result_summary: str = "",
        topic: str = "",
        **kwargs,
    ) -> ToolResult:
        if not query or not lesson:
            return ToolResult(success=False, error="query and lesson are required")

        # Build rich embedding text
        embed_parts = [f"Topic: {query}"]
        if lesson:
            embed_parts.append(f"Lesson: {lesson}")
        if anti_pattern:
            embed_parts.append(f"Warning: {anti_pattern}")
        embed_parts.append(f"Outcome: {outcome_type}")
        text_to_embed = "\n".join(embed_parts)

        embedding = generate_embedding(text_to_embed)

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_memory
                    (query, action, result_summary, lesson, outcome_type,
                     confidence, topic, anti_pattern, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                query,
                action,
                result_summary,
                lesson,
                outcome_type,
                confidence,
                topic or query,
                anti_pattern,
                str(embedding),
            )

        return ToolResult(success=True, data={"stored": True})


class RecallMemoryTool(BaseTool):
    """Retrieve relevant lessons from past research sessions."""

    @property
    def name(self) -> str:
        return "recall_memory"

    @property
    def description(self) -> str:
        return "Retrieve lessons from past sessions relevant to the current query."

    async def execute(
        self,
        query: str = "",
        k: int = 5,
        **kwargs,
    ) -> ToolResult:
        if not query:
            return ToolResult(success=False, error="Query is required")

        embedding = generate_embedding(f"Topic: {query}")

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT query, action, result_summary, lesson, outcome_type,
                       confidence, anti_pattern,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM agent_memory
                WHERE (lesson IS NOT NULL AND lesson != '')
                   OR (anti_pattern IS NOT NULL AND anti_pattern != '')
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                str(embedding),
                k,
            )

        lessons = [dict(r) for r in rows]
        return ToolResult(
            success=True,
            data=lessons,
            metadata={"query": query[:100], "k": k, "results": len(lessons)},
        )
