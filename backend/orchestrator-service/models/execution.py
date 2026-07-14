"""
Execution tracking models — events, checkpoints, errors.

These models power observability, crash recovery, and debugging.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class EventType(str, Enum):
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_RETRYING = "node_retrying"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    STATE_UPDATED = "state_updated"
    CHECKPOINT_SAVED = "checkpoint_saved"
    TASK_RESUMED = "task_resumed"


class ExecutionEvent(BaseModel):
    """A single event in the task's execution history."""

    event_type: EventType
    node_id: str = ""
    worker_name: str = ""
    tool_name: str = ""
    message: str = ""
    duration_ms: int = 0
    tokens_used: int = 0
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Checkpoint(BaseModel):
    """
    A snapshot of task state at a specific point in the execution graph.

    Used for crash recovery — the engine can resume from the latest
    valid checkpoint instead of re-running the entire pipeline.
    """

    checkpoint_id: str = ""
    node_id: str
    status: str = "saved"
    state_version: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ErrorEvent(BaseModel):
    """A structured error record for failure diagnostics."""

    node_id: str
    worker_name: str = ""
    error_type: str = ""  # TimeoutError, LLMError, etc.
    error_message: str = ""
    traceback: str = ""
    retry_count: int = 0
    recoverable: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)
