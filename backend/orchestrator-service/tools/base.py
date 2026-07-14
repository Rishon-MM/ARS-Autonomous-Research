"""
tools/base.py — Base class for all tools.

Every tool must declare its name, description, and implement __call__.
Tools are stateless and instrumented with tracing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import time
import logging

log = logging.getLogger("ars.tools")


@dataclass
class ToolResult:
    """Standardized result from any tool invocation."""

    success: bool
    data: Any = None
    error: str = ""
    duration_ms: int = 0
    metadata: dict = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (e.g., 'search_web', 'retrieve_chunks')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Run the tool with the given parameters."""
        ...

    async def __call__(self, **kwargs) -> ToolResult:
        """Instrumented invocation — wraps execute with timing and logging."""
        start = time.monotonic()
        try:
            result = await self.execute(**kwargs)
            result.duration_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "Tool %s completed in %dms (success=%s)",
                self.name,
                result.duration_ms,
                result.success,
            )
            return result
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            log.error("Tool %s failed after %dms: %s", self.name, duration, e)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration,
            )
