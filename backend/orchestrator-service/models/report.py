"""
Report domain models — outlines, sections, and final report structure.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    """A single section of the research report."""

    section_name: str
    target_words: int = 300
    summary: str = ""  # purpose / what to cover
    content: str = ""  # written content
    citations_used: list[str] = Field(default_factory=list)  # citation_ids
    verified_claim_ids: list[str] = Field(default_factory=list)
    written: bool = False


class ReportOutline(BaseModel):
    """The full report outline produced by the writer's planning step."""

    title: str
    sections: list[ReportSection] = Field(default_factory=list)
    total_target_words: int = 2000
