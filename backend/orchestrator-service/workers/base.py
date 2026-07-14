"""
workers/base.py — Abstract base class for all workers.

Workers are the core computational units of the graph.
They read from TaskState, invoke tools, and return state mutations.
Workers never communicate with each other directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from models.task_state import TaskState
from tools.registry import ToolRegistry


@dataclass
class WorkerResult:
    """Result of a worker execution."""

    success: bool
    state_updates: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)  # SSE events to stream
    error: str = ""
    tokens_used: int = 0
    tool_calls: list[dict] = field(default_factory=list)

    def add_event(self, event_type: str, **data) -> None:
        self.events.append({"type": event_type, **data})


class BaseWorker(ABC):
    """
    Abstract base class for all workers.

    Subclasses must implement:
    - execute(): perform the work, return a WorkerResult
    - reads: list of TaskState fields this worker reads
    - writes: list of TaskState fields this worker writes
    """

    @abstractmethod
    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        """
        Read state, invoke tools, produce results.

        The worker MUST NOT modify state directly.  Instead, it
        returns a WorkerResult containing state_updates, which
        the graph engine applies atomically.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Worker name (e.g., 'planner', 'researcher')."""
        ...

    @property
    @abstractmethod
    def reads(self) -> list[str]:
        """TaskState fields this worker reads."""
        ...

    @property
    @abstractmethod
    def writes(self) -> list[str]:
        """TaskState fields this worker writes."""
        ...
