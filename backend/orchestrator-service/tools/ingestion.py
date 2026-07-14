"""
tools/ingestion.py — PDF ingestion tool.

Downloads PDFs, extracts text, chunks, embeds, and stores in pgvector.
Refactored from search-service/ingestion.py into a callable tool.
"""

from __future__ import annotations

import hashlib
import os
import re
import logging

import httpx
import fitz  # PyMuPDF

from .base import BaseTool, ToolResult
from .retrieval import generate_embedding
from db.connection import get_pool

log = logging.getLogger("ars.tools.ingestion")

PDF_STORAGE_DIR = os.getenv("PDF_STORAGE_DIR", "/app/pdfs")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MAX_PDF_SIZE_MB = 50


# ── Pipeline helpers ──────────────────────────────────────────────

async def download_pdf(url: str, paper_id: str) -> str | None:
    """Download a PDF and save to persistent storage.  Returns local path."""
    os.makedirs(PDF_STORAGE_DIR, exist_ok=True)
    safe_name = re.sub(r'[^\w\-.]', '_', paper_id)[:80]
    local_path = os.path.join(PDF_STORAGE_DIR, f"{safe_name}.pdf")

    if os.path.exists(local_path):
        log.debug("PDF already exists: %s", local_path)
        return local_path

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=60.0,
            headers={"User-Agent": "ARS-Research-Assistant/1.0"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            if len(response.content) > MAX_PDF_SIZE_MB * 1024 * 1024:
                log.warning("PDF too large: %d bytes", len(response.content))
                return None

            if not response.content[:5].startswith(b"%PDF"):
                log.warning("URL did not return a valid PDF: %s", url)
                return None

            with open(local_path, "wb") as f:
                f.write(response.content)

            log.info("Downloaded PDF: %s (%d bytes)", local_path, len(response.content))
            return local_path
    except Exception as e:
        log.error("Failed to download %s: %s", url, e)
        return None


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        pages = [page.get_text("text") for page in doc if page.get_text("text").strip()]
        doc.close()
        combined = "\n".join(pages)
        combined = re.sub(r'\n{3,}', '\n\n', combined)
        combined = re.sub(r'[ \t]+', ' ', combined)
        return combined.strip()
    except Exception as e:
        log.error("Failed to extract text from %s: %s", pdf_path, e)
        return ""


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks by word count."""
    if not text:
        return []
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if len(chunk.split()) > 30:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


async def store_chunks(paper_id: str, title: str, chunks: list[str]) -> int:
    """Embed and store text chunks in pgvector.  Returns count stored."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM paper_chunks WHERE paper_id = $1", paper_id
        )
        if existing and existing > 0:
            log.info("Paper %r already has %d chunks, skipping", paper_id, existing)
            return existing

        stored = 0
        for chunk in chunks:
            try:
                embedding = generate_embedding(chunk)
                await conn.execute(
                    """
                    INSERT INTO paper_chunks (paper_id, title, chunk, embedding)
                    VALUES ($1, $2, $3, $4)
                    """,
                    paper_id,
                    title,
                    chunk,
                    str(embedding),
                )
                stored += 1
            except Exception as e:
                log.error("Failed to store chunk: %s", e)

    log.info("Stored %d chunks for %r", stored, title[:60])
    return stored


# ── Tool class ────────────────────────────────────────────────────

class IngestionTool(BaseTool):
    """Ingest a single paper: download PDF → extract → chunk → embed → store."""

    @property
    def name(self) -> str:
        return "ingest_document"

    @property
    def description(self) -> str:
        return "Download a PDF, extract text, chunk it, and store embeddings in the knowledge base."

    async def execute(
        self,
        title: str = "Unknown",
        pdf_url: str = "",
        paper_id: str = "",
        arxiv_id: str = "",
        venue: str = "",
        **kwargs,
    ) -> ToolResult:
        if not pdf_url:
            # Try to construct arXiv PDF URL
            if arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            else:
                return ToolResult(
                    success=False,
                    error="No PDF URL and no arXiv ID provided",
                )

        if not paper_id:
            paper_id = arxiv_id or hashlib.md5(title.encode()).hexdigest()[:16]

        # Step 1: Download
        local_path = await download_pdf(pdf_url, paper_id)
        if not local_path:
            return ToolResult(
                success=False,
                error="Download failed",
                metadata={"paper_id": paper_id, "title": title},
            )

        # Step 2: Extract
        text = extract_text_from_pdf(local_path)
        if not text or len(text) < 200:
            return ToolResult(
                success=False,
                error="Extraction produced insufficient text",
                metadata={"paper_id": paper_id, "text_length": len(text)},
            )

        # Step 3: Chunk
        chunks = chunk_text(text)
        if not chunks:
            return ToolResult(
                success=False,
                error="No chunks produced",
                metadata={"paper_id": paper_id},
            )

        # Step 4: Store
        stored = await store_chunks(paper_id, title, chunks)

        return ToolResult(
            success=True,
            data={
                "paper_id": paper_id,
                "title": title,
                "chunks_stored": stored,
                "text_length": len(text),
            },
        )
