"""
tools/search.py — Web search trigger tool.

Triggers a search via the knowledge crawler subsystem and returns results.
This is a lightweight coordination tool — the actual browser automation
lives in the knowledge/ layer.
"""

from __future__ import annotations

import json
import logging
import httpx

from .base import BaseTool, ToolResult

log = logging.getLogger("ars.tools.search")


class SearchWebTool(BaseTool):
    """Trigger an academic paper search and return results."""

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "Search for academic papers on a given topic via the knowledge crawler."

    async def execute(
        self,
        query: str = "",
        crawler=None,
        **kwargs,
    ) -> ToolResult:
        """
        If a crawler instance is provided, use it directly.
        Otherwise, fall back to HTTP call to the search endpoint.
        """
        if not query:
            return ToolResult(success=False, error="Query is required")

        if crawler is not None:
            # Direct invocation (in-process)
            try:
                result = await crawler.crawl([query])
                return ToolResult(
                    success=True,
                    data=result,
                    metadata={"query": query, "method": "direct"},
                )
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        # HTTP fallback (for backward compatibility)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                papers = []
                async with client.stream(
                    "GET",
                    "http://localhost:8003/api/papers/search",
                    params={"q": query},
                ) as response:
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        while "\n\n" in buffer:
                            event, buffer = buffer.split("\n\n", 1)
                            if event.startswith("data: "):
                                try:
                                    data = json.loads(event[6:])
                                    if data.get("type") == "final_result":
                                        papers = data.get("papers", [])
                                except json.JSONDecodeError:
                                    pass
                return ToolResult(
                    success=True,
                    data=papers,
                    metadata={"query": query, "method": "http", "count": len(papers)},
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
