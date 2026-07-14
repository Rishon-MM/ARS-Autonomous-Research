"""
tools/registry.py — Central registry for all available tools.

Workers request tools by name from the registry.
The registry is populated at startup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseTool, ToolResult

log = logging.getLogger("ars.tools.registry")


class ToolRegistry:
    """
    Central tool registry.

    Workers call `registry.get("tool_name")` to obtain a tool instance,
    then invoke it with `await tool(param=value)`.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            log.warning("Tool %r already registered — overwriting", tool.name)
        self._tools[tool.name] = tool
        log.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool:
        """Get a tool by name.  Raises KeyError if not found."""
        if name not in self._tools:
            available = ", ".join(sorted(self._tools.keys()))
            raise KeyError(
                f"Tool {name!r} not found.  Available: {available}"
            )
        return self._tools[name]

    def list_tools(self) -> list[dict]:
        """Return metadata for all registered tools."""
        return [
            {"name": t.name, "description": t.description}
            for t in self._tools.values()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
