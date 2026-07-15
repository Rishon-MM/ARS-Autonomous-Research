"""
workers/editor.py — Editor Worker

Reads: report_outline, report_sections, search_results, citations
Writes: final_report
Tools: call_llm
"""

from __future__ import annotations

import json
import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.report_writer import EDITOR_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.editor")


class EditorWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "editor"

    @property
    def reads(self) -> list[str]:
        return ["report_outline", "report_sections", "citations", "search_results"]

    @property
    def writes(self) -> list[str]:
        return ["final_report"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        llm = tools.get("call_llm")
        editor_provider = state.agent_providers.get("Editor", state.provider)

        result.add_event(
            "agent_status",
            agent="Editor",
            state="working",
            statusText="Polishing full report...",
            subText="Improving transitions & consistency",
        )

        # Build sources list for references
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

        references_text = "\n".join(
            f"[{i+1}] {s.get('title', 'Unknown')} ({s.get('year', '')})"
            for i, s in enumerate(sources)
        )

        # Assemble sections for the editor
        # Ensure we use the outline order
        sections_for_editor = []
        for section_obj in state.report_outline.sections:
            name = section_obj.section_name
            content = state.report_sections.get(name, "[Section missing]")
            sections_for_editor.append({
                "section": name,
                "content": content
            })

        editor_input = json.dumps({
            "title": state.report_title,
            "sections": sections_for_editor,
            "references": references_text,
        })

        editor_result = await llm(
            system_prompt=EDITOR_SYSTEM_PROMPT,
            user_input=editor_input,
            provider=editor_provider,
            tier="strong",
            json_output=True,
            temperature=state.agent_temperatures.get("Editor", 0.3),
        )

        if not editor_result.success:
            # Fall back to concatenation
            final_report = f"# {state.report_title}\n\n"
            for s in sections_for_editor:
                final_report += f"## {s['section']}\n\n{s['content']}\n\n"
        else:
            editor_data = parse_llm_json(editor_result.data)
            final_report = editor_data.get("report", "")

        result.success = True
        result.state_updates = {
            "final_report": final_report,
        }

        result.add_event(
            "agent_status",
            agent="Editor",
            state="complete",
            statusText="Report Polished",
            subText="Final document ready",
        )

        log.info(
            "Report polished: title=%r, sections=%d, length=%d chars",
            state.report_title[:60],
            len(sections_for_editor),
            len(final_report),
        )
        return result
