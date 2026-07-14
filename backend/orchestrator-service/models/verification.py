"""
Verification domain models — evidence-first claim verification.

Every claim entering the report must pass through verification.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from .research import Evidence


class VerifiedClaim(BaseModel):
    """
    A claim that has been verified against evidence.

    No claim may enter report generation without at least one piece
    of supporting evidence and a confidence score.
    """

    claim_id: str = ""
    claim: str
    evidence: list[Evidence] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0  # 0.0–1.0
    verification_method: str = "evidence_match"  # evidence_match | cross_reference | llm_check
    verified: bool = False
    rejection_reason: str = ""


class VerificationResult(BaseModel):
    """Aggregate output of the Verification worker."""

    total_claims: int = 0
    verified_count: int = 0
    rejected_count: int = 0
    average_confidence: float = 0.0
    claims: list[VerifiedClaim] = Field(default_factory=list)
    unverifiable_claims: list[str] = Field(
        default_factory=list,
        description="Claims that could not be verified due to missing evidence",
    )
