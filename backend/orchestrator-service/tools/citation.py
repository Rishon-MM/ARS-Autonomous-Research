"""
tools/citation.py — Citation verification tool.

Verifies that a claim is supported by the cited evidence.
"""

from __future__ import annotations

import logging
from .base import BaseTool, ToolResult

log = logging.getLogger("ars.tools.citation")


class CitationVerificationTool(BaseTool):
    """Verify that a citation's evidence supports the associated claim."""

    @property
    def name(self) -> str:
        return "verify_citation"

    @property
    def description(self) -> str:
        return "Check if a claim is supported by its cited evidence."

    async def execute(
        self,
        claim: str = "",
        evidence_texts: list[str] | None = None,
        source_ids: list[str] | None = None,
        **kwargs,
    ) -> ToolResult:
        """
        Simple heuristic verification:
        - Check that evidence is non-empty
        - Check that evidence text has meaningful overlap with claim keywords
        - Return a confidence score

        For production, this would integrate with the LLM tool for
        semantic verification.
        """
        if not claim:
            return ToolResult(success=False, error="Claim text is required")

        evidence_texts = evidence_texts or []
        source_ids = source_ids or []

        if not evidence_texts:
            return ToolResult(
                success=True,
                data={
                    "verified": False,
                    "confidence": 0.0,
                    "reason": "No evidence provided",
                },
            )

        # Keyword overlap heuristic
        claim_words = set(claim.lower().split())
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "of", "in", "to", "and", "for", "on", "with", "that", "this", "it"}
        claim_keywords = claim_words - stop_words

        if not claim_keywords:
            return ToolResult(
                success=True,
                data={"verified": True, "confidence": 0.3, "reason": "Claim too generic to verify"},
            )

        total_overlap = 0
        for evidence in evidence_texts:
            evidence_words = set(evidence.lower().split())
            overlap = len(claim_keywords & evidence_words)
            total_overlap += overlap

        # Confidence based on keyword coverage
        coverage = min(total_overlap / max(len(claim_keywords), 1), 1.0)
        confidence = round(coverage * 0.8 + 0.1 * len(evidence_texts), 2)
        confidence = min(confidence, 1.0)

        verified = confidence >= 0.3 and len(evidence_texts) > 0

        return ToolResult(
            success=True,
            data={
                "verified": verified,
                "confidence": confidence,
                "evidence_count": len(evidence_texts),
                "source_ids": source_ids,
                "reason": "Evidence supports claim" if verified else "Insufficient evidence overlap",
            },
        )
