"""
Evaluation and reflection domain models.

Every completed task produces quantitative metrics and a structured
reflection record that feeds back into future planning.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime


class EvaluationMetrics(BaseModel):
    """Quantitative evaluation of a completed research task."""

    task_success: float = 0.0          # overall success score 0–1
    citation_accuracy: float = 0.0     # verified citations / total citations
    source_coverage: float = 0.0       # sources cited / sources available
    verification_rate: float = 0.0     # verified claims / total claims
    tool_efficiency: float = 0.0       # useful tool calls / total tool calls
    latency: float = 0.0              # total execution time in seconds
    cost: float = 0.0                 # estimated cost (tokens × price)
    research_completeness: float = 0.0 # questions answered / total questions

    # Breakdowns
    total_tokens_used: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    total_retrieval_calls: int = 0
    total_claims: int = 0
    verified_claims: int = 0
    rejected_claims: int = 0


class ReflectionRecord(BaseModel):
    """
    Structured reflection that improves future planning.

    Unlike vague "lessons learned", this captures concrete strategies
    with quantitative backing.
    """

    outcome_type: str = "mixed"  # success | failure | mixed
    confidence: float = 0.5

    successful_strategies: list[str] = Field(default_factory=list)
    failed_strategies: list[str] = Field(default_factory=list)

    retrieval_quality: dict = Field(
        default_factory=dict,
        description="avg_similarity, coverage, gaps identified",
    )
    verification_outcomes: dict = Field(
        default_factory=dict,
        description="pass_rate, common rejection reasons",
    )

    planning_feedback: str = ""  # concrete advice for future planner
    query_refinement_suggestions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
