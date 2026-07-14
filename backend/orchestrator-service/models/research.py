"""
Research domain models — plans, findings, evidence, citations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime


class ResearchQuestion(BaseModel):
    """A single research question derived from the user query."""

    question: str
    priority: int = 0  # higher = more important
    answered: bool = False


class ResearchPlan(BaseModel):
    """Output of the Planner worker."""

    topic: str
    goal: str
    research_questions: list[ResearchQuestion] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    desired_sections: list[str] = Field(default_factory=list)
    sub_tasks: list[str] = Field(
        default_factory=list,
        description="Decomposed sub-queries for parallel research nodes",
    )


class SearchResult(BaseModel):
    """A single result from a web/arXiv search."""

    title: str
    url: str = ""
    pdf_url: str = ""
    source_type: str = "paper"  # paper | article | website
    authors: list[str] = Field(default_factory=list)
    year: int = 0
    venue: str = ""
    abstract: str = ""
    arxiv_id: str = ""


class RetrievedChunk(BaseModel):
    """A chunk retrieved from the pgvector knowledge base."""

    paper_id: str
    title: str
    chunk: str
    similarity: float = 0.0
    source_query: str = ""


class Evidence(BaseModel):
    """A piece of evidence supporting a finding or claim."""

    evidence_id: str = Field(default_factory=lambda: "")
    text: str
    source_id: str  # paper_id or URL
    source_title: str = ""
    chunk_similarity: float = 0.0
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class Citation(BaseModel):
    """An APA-formatted citation with tracking metadata."""

    citation_id: str = ""
    source_id: str  # links to SearchResult or paper_id
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int = 0
    venue: str = ""
    url: str = ""
    apa_text: str = ""  # pre-formatted APA string
    cited_in_sections: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    """A synthesized finding from the Research worker."""

    finding_id: str = ""
    claim: str
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0  # 0.0–1.0
    sub_task: str = ""  # which sub-query produced this
    research_question: str = ""  # which question this answers
