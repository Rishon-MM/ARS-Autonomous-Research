"""
tools/retrieval.py — Vector similarity retrieval from pgvector.

Retrieves the most relevant paper chunks for a given query.
"""

from __future__ import annotations

import logging
from sentence_transformers import SentenceTransformer

from .base import BaseTool, ToolResult
from db.connection import get_pool

log = logging.getLogger("ars.tools.retrieval")

# Lazily loaded embedding model
_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        log.info("Loaded embedding model: all-MiniLM-L6-v2")
    return _embed_model


def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dim embedding for the given text."""
    model = _get_embed_model()
    return model.encode(text).tolist()


class RetrievalTool(BaseTool):
    """Retrieve relevant paper chunks from pgvector knowledge base."""

    @property
    def name(self) -> str:
        return "retrieve_chunks"

    @property
    def description(self) -> str:
        return "Retrieve the most relevant paper chunks from the vector knowledge base."

    async def execute(
        self,
        query: str = "",
        k: int = 5,
        **kwargs,
    ) -> ToolResult:
        if not query:
            return ToolResult(success=False, error="Query cannot be empty")

        embedding = generate_embedding(query)

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT paper_id, title, chunk,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM paper_chunks
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                str(embedding),
                k,
            )

        chunks = [
            {
                "paper_id": r["paper_id"],
                "title": r["title"],
                "chunk": r["chunk"],
                "similarity": float(r["similarity"]),
            }
            for r in rows
        ]

        return ToolResult(
            success=True,
            data=chunks,
            metadata={"query": query[:100], "k": k, "results": len(chunks)},
        )


class KnowledgeStatsTool(BaseTool):
    """Get statistics about the knowledge base."""

    @property
    def name(self) -> str:
        return "knowledge_stats"

    @property
    def description(self) -> str:
        return "Return total chunks and papers in the knowledge base."

    async def execute(self, **kwargs) -> ToolResult:
        pool = await get_pool()
        async with pool.acquire() as conn:
            total_chunks = await conn.fetchval("SELECT COUNT(*) FROM paper_chunks")
            total_papers = await conn.fetchval(
                "SELECT COUNT(DISTINCT paper_id) FROM paper_chunks"
            )

        return ToolResult(
            success=True,
            data={
                "total_chunks": total_chunks or 0,
                "total_papers": total_papers or 0,
            },
        )
