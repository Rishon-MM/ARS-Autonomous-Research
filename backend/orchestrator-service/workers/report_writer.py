"""
workers/report_writer.py — Report Writer Worker

Reads: plan, verified_claims, citations
Writes: report_outline, report_sections, final_report, report_title
Tools: call_llm, retrieve_chunks

Combines outliner, section writer, and editor into a single worker
that produces the final report from verified claims.
"""

from __future__ import annotations

import json
import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from models.report import ReportOutline, ReportSection
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.report_writer import (
    OUTLINER_SYSTEM_PROMPT,
    SECTION_WRITER_SYSTEM_PROMPT,
    EDITOR_SYSTEM_PROMPT,
)

log = logging.getLogger("ars.workers.report_writer")


class ReportWriterWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "report_writer"

    @property
    def reads(self) -> list[str]:
        return ["plan", "verified_claims", "citations", "search_results"]

    @property
    def writes(self) -> list[str]:
        return ["report_outline", "report_sections", "final_report", "report_title"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        llm = tools.get("call_llm")
        retrieval = tools.get("retrieve_chunks")
        provider = state.agent_providers.get("Writer", state.provider)
        editor_provider = state.agent_providers.get("Editor", state.provider)

        # ── Step 1: Outline ───────────────────────────────────────
        result.add_event(
            "agent_status",
            agent="Writer",
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
        # Also build from citations
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
            agent="Writer",
            state="working",
            statusText="Outline ready",
            subText=f"{len(sections)} sections planned",
        )

        # ── Step 2: Write each section ────────────────────────────
        written_sections = {}
        total = len(sections)

        # Build references for citation
        references_text = "\n".join(
            f"[{i+1}] {s.get('title', 'Unknown')} ({s.get('year', '')})"
            for i, s in enumerate(sources)
        )

        for idx, section in enumerate(sections):
            result.add_event(
                "agent_status",
                agent="Writer",
                state="working",
                statusText=f"Writing: {section.section_name}",
                subText=f"Section {idx + 1} of {total}",
            )

            # Retrieve relevant chunks for this section
            rag_context = ""
            if retrieval and not state.library_only:
                section_query = f"{state.query} {section.section_name} {section.summary}"
                rag_result = await retrieval(query=section_query, k=5)
                if rag_result.success and rag_result.data:
                    rag_parts = []
                    for i, chunk in enumerate(rag_result.data):
                        rag_parts.append(
                            f"[Source {i+1}] (Paper: {chunk.get('title', 'Unknown')}, "
                            f"Relevance: {chunk.get('similarity', 0):.2f})\n"
                            f"{chunk.get('chunk', '')}"
                        )
                    rag_context = "\n\n---\n\n".join(rag_parts)
                    result.tool_calls.append({
                        "tool": "retrieve_chunks",
                        "section": section.section_name,
                        "chunks": len(rag_result.data),
                    })

            # Build verified claims for this section
            relevant_claims = [
                f"- {vc.claim} (confidence: {vc.confidence:.1%})"
                for vc in state.verified_claims
                if vc.verified
            ]

            writer_input = (
                f"Section to write: {section.section_name}\n\n"
                f"Section summary/purpose: {section.summary}\n\n"
                f"Target word count: {section.target_words}\n\n"
            )

            if relevant_claims:
                writer_input += (
                    "=== VERIFIED CLAIMS (use these as the foundation) ===\n"
                    + "\n".join(relevant_claims) + "\n\n"
                )

            if rag_context:
                writer_input += f"=== KNOWLEDGE BASE CONTEXT ===\n{rag_context}\n\n"

            writer_input += f"Available sources (use [N] for inline citations):\n{references_text}\n"

            section_result = await llm(
                system_prompt=SECTION_WRITER_SYSTEM_PROMPT,
                user_input=writer_input,
                provider=provider,
                tier="strong",
                json_output=False,
                temperature=state.agent_temperatures.get("Writer", 0.5),
            )

            if section_result.success:
                written_sections[section.section_name] = section_result.data
            else:
                written_sections[section.section_name] = f"[Section writing failed: {section_result.error}]"

        result.add_event(
            "agent_status",
            agent="Writer",
            state="working",
            statusText="All sections written",
            subText=f"Editing {total} sections into final report",
        )

        # ── Step 3: Edit into final report ────────────────────────
        result.add_event(
            "agent_status",
            agent="Editor",
            state="working",
            statusText="Polishing full report...",
            subText="Improving transitions & consistency",
        )

        sections_for_editor = [
            {"section": name, "content": content}
            for name, content in written_sections.items()
        ]

        editor_input = json.dumps({
            "title": report_title,
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
            final_report = f"# {report_title}\n\n"
            for name, content in written_sections.items():
                final_report += f"## {name}\n\n{content}\n\n"
        else:
            editor_data = parse_llm_json(editor_result.data)
            final_report = editor_data.get("report", "")

        result.success = True
        result.state_updates = {
            "report_outline": outline,
            "report_sections": written_sections,
            "final_report": final_report,
            "report_title": report_title,
        }

        result.add_event(
            "agent_status",
            agent="Editor",
            state="complete",
            statusText="Report Polished",
            subText="Final document ready",
        )

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

        log.info(
            "Report written: title=%r, sections=%d, length=%d chars",
            report_title[:60],
            len(written_sections),
            len(final_report),
        )
        return result
