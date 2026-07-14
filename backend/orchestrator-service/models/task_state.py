"""
TaskState — the single source of truth for any research task.

All workers read from and write to this model via the StateManager.
The orchestrator serializes this to PostgreSQL after every node execution.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

from .research import (
    ResearchPlan,
    Finding,
    Evidence,
    SearchResult,
    RetrievedChunk,
    Citation,
)
from .verification import VerifiedClaim
from .report import ReportOutline
from .evaluation import EvaluationMetrics, ReflectionRecord
from .execution import ExecutionEvent, Checkpoint, ErrorEvent


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    SEARCHING = "searching"
    RESEARCHING = "researching"
    VERIFYING = "verifying"
    WRITING = "writing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    RESUMING = "resuming"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class TaskState(BaseModel):
    """
    Centralized shared state for a research task.

    This is the ONLY data structure that workers interact with.
    Workers read the fields they need and write their results.
    The orchestrator persists this to PostgreSQL after every node.

    Versioned with optimistic locking — every save increments `version`.
    """

    # ── Identity ─────────────────────────────────────────────────
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    status: TaskStatus = TaskStatus.PENDING
    version: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # ── Configuration ────────────────────────────────────────────
    provider: str = "gemini"
    agent_providers: dict[str, str] = Field(default_factory=dict)
    agent_temperatures: dict[str, float] = Field(default_factory=dict)
    library_only: bool = False
    library_papers: list[dict] = Field(default_factory=list)

    # ── Planner output ───────────────────────────────────────────
    plan: ResearchPlan | None = None

    # ── Knowledge acquisition ────────────────────────────────────
    search_results: list[SearchResult] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)

    # ── Research output ──────────────────────────────────────────
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    # ── Verification output ──────────────────────────────────────
    verified_claims: list[VerifiedClaim] = Field(default_factory=list)

    # ── Report output ────────────────────────────────────────────
    report_outline: ReportOutline | None = None
    report_sections: dict[str, str] = Field(default_factory=dict)
    final_report: str = ""
    report_title: str = ""

    # ── Evaluation & reflection ──────────────────────────────────
    metrics: EvaluationMetrics | None = None
    reflection: ReflectionRecord | None = None

    # ── Execution tracking ───────────────────────────────────────
    execution_log: list[ExecutionEvent] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    error_log: list[ErrorEvent] = Field(default_factory=list)
    node_statuses: dict[str, str] = Field(
        default_factory=dict,
        description="Map of node_id → NodeStatus value",
    )

    # ── Timing ───────────────────────────────────────────────────
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def mark_started(self) -> None:
        self.started_at = datetime.utcnow()
        self.status = TaskStatus.PLANNING

    def mark_completed(self) -> None:
        self.completed_at = datetime.utcnow()
        self.status = TaskStatus.COMPLETED

    def mark_failed(self, error: str = "") -> None:
        self.completed_at = datetime.utcnow()
        self.status = TaskStatus.FAILED
        if error:
            self.error_log.append(
                ErrorEvent(
                    node_id="task",
                    error_type="TaskFailure",
                    error_message=error,
                )
            )

    def bump_version(self) -> None:
        self.version += 1
        self.updated_at = datetime.utcnow()
