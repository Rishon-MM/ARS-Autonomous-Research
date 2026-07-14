"""
graph/node.py — Graph node definition.

Each node wraps a worker and carries metadata for dependency tracking,
retry policies, timeouts, and execution status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

from models.task_state import NodeStatus

if TYPE_CHECKING:
    from workers.base import BaseWorker


@dataclass
class RetryPolicy:
    """Configurable retry behavior for a node."""

    max_retries: int = 3
    backoff: str = "exponential"  # exponential | linear | fixed
    base_delay: float = 1.0       # seconds
    max_delay: float = 60.0       # seconds

    def delay_for_attempt(self, attempt: int) -> float:
        """Compute delay for the given retry attempt (0-indexed)."""
        if self.backoff == "exponential":
            delay = self.base_delay * (2 ** attempt)
        elif self.backoff == "linear":
            delay = self.base_delay * (attempt + 1)
        else:
            delay = self.base_delay
        return min(delay, self.max_delay)


@dataclass
class GraphNode:
    """
    A single node in the execution graph.

    Encapsulates a worker, its dependencies, retry behavior,
    and current execution status.
    """

    node_id: str
    worker: BaseWorker
    dependencies: list[str] = field(default_factory=list)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=120))
    status: NodeStatus = NodeStatus.PENDING
    retry_count: int = 0

    # Set by the engine after execution
    duration_ms: int = 0
    error: str = ""

    def dependencies_met(self, completed_nodes: set[str]) -> bool:
        """Check if all dependency nodes have completed."""
        return all(dep in completed_nodes for dep in self.dependencies)

    def can_retry(self) -> bool:
        """Check if this node can be retried."""
        return self.retry_count < self.retry_policy.max_retries

    def mark_running(self) -> None:
        self.status = NodeStatus.RUNNING

    def mark_completed(self, duration_ms: int = 0) -> None:
        self.status = NodeStatus.COMPLETED
        self.duration_ms = duration_ms

    def mark_failed(self, error: str = "") -> None:
        self.status = NodeStatus.FAILED
        self.error = error

    def mark_retrying(self) -> None:
        self.status = NodeStatus.RETRYING
        self.retry_count += 1
