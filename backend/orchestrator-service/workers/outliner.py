"""
workers/outliner.py — Outliner Worker

Reads: plan, verified_claims, search_results, citations
Writes: report_outline, report_title
Tools: call_llm
"""

from __future__ import annotations

import json
import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from models.report import ReportOutline, ReportSection
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.outliner import OUTLINER_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.outliner")


class OutlinerWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "outliner"

    @property
    def reads(self) -> list[str]:
        return ["plan", "verified_claims", "citations", "search_results"]

    @property
    def writes(self) -> list[str]:
        return ["report_outline", "report_title"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        llm = tools.get("call_llm")
        provider = state.agent_providers.get("Writer", state.provider)

        result.add_event(
            "agent_status",
            agent="Outliner",
            state="working",
            statusText="Creating report outline...",
            subText="Structuring sections",
        )

        # Build sources list from search results + citations
        sources = []
        for sr in state.search_results:
            sources.append({
                "title": sr.title,
                "url": sr.url,
                "authors": sr.authors,
                "year": sr.year,
            })
        for c in state.citations:
            if not any(s["title"] == c.title for s in sources):
                sources.append({
                    "title": c.title,
                    "url": c.url,
                    "authors": c.authors,
                    "year": c.year,
                })

        # Include verified claims summary for the outliner
        claims_summary = [
            {"claim": vc.claim, "confidence": vc.confidence}
            for vc in state.verified_claims
            if vc.verified
        ]

        outliner_input = json.dumps({
            "topic": state.plan.topic if state.plan else state.query,
            "goal": state.plan.goal if state.plan else "",
            "desired_sections": state.plan.desired_sections if state.plan else [],
            "verified_claims": claims_summary,
            "sources": sources,
        })

        outliner_result = await llm(
            system_prompt=OUTLINER_SYSTEM_PROMPT,
            user_input=outliner_input,
            provider=provider,
            tier="fast",
            json_output=True,
            temperature=state.agent_temperatures.get("Writer", 0.5),
        )

        if not outliner_result.success:
            result.error = f"Outliner failed: {outliner_result.error}"
            return result

        outline_data = parse_llm_json(outliner_result.data)
        sections = [
            ReportSection(
                section_name=s.get("section_name", s.get("section", f"Section {i}")),
                target_words=s.get("target_words", 300),
                summary=s.get("summary", ""),
            )
            for i, s in enumerate(outline_data.get("sections", outline_data.get("outline", [])))
        ]
        report_title = outline_data.get("title", state.query)
        outline = ReportOutline(title=report_title, sections=sections)

        result.add_event(
            "agent_status",
            agent="Outliner",
            state="complete",
            statusText="Outline ready",
            subText=f"{len(sections)} sections planned",
        )

        result.success = True
        result.state_updates = {
            "report_outline": outline,
            "report_title": report_title,
        }

        # Send sources to frontend
        frontend_sources = [
            {
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "source_type": "paper",
                "key_points": [],
                "citation": f"{', '.join(s.get('authors', [])[:3])} ({s.get('year', '')}). {s.get('title', '')}.",
            }
            for s in sources
        ]
        result.add_event("sources_update", sources=frontend_sources)

        log.info("Outline created: title=%r, sections=%d", report_title[:60], len(sections))
        return result
