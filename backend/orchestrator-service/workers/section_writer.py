"""
workers/section_writer.py — Section Writer Worker

Reads: report_outline, verified_claims, citations
Writes: report_sections
Tools: call_llm, retrieve_chunks
"""

from __future__ import annotations

import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from tools.registry import ToolRegistry
from prompts.report_writer import SECTION_WRITER_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.section_writer")


class SectionWriterWorker(BaseWorker):
    def __init__(self, section_name: str, section_index: int, total_sections: int):
        self.section_name = section_name
        self.section_index = section_index
        self.total_sections = total_sections

    @property
    def name(self) -> str:
        return f"section_writer_{self.section_index}"

    @property
    def reads(self) -> list[str]:
        return ["report_outline", "verified_claims", "citations", "search_results"]

    @property
    def writes(self) -> list[str]:
        return ["report_sections"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        llm = tools.get("call_llm")
        retrieval = tools.get("retrieve_chunks")
        provider = state.agent_providers.get("Writer", state.provider)

        result.add_event(
            "agent_status",
            agent="Section Writer",
            state="working",
            statusText=f"Writing: {self.section_name}",
            subText=f"Section {self.section_index + 1} of {self.total_sections}",
        )

        # Find the specific section in the outline
        section = None
        for s in state.report_outline.sections:
            if s.section_name == self.section_name:
                section = s
                break
                
        if not section:
            result.error = f"Section '{self.section_name}' not found in outline"
            return result

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

        references_text = "\n".join(
            f"[{i+1}] {s.get('title', 'Unknown')} ({s.get('year', '')})"
            for i, s in enumerate(sources)
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

        # For the state updates, we only update this specific section
        # Because we're modifying a dictionary in the TaskState, we will need to merge it in the engine
        # However, the engine's `_execute_node` already does `setattr(state, field, new_val)`.
        # For dictionary merging, we can rely on Pydantic and dict updates if we emit the partial dict.
        # Wait, if we just output the dict with one key, it will replace the whole dict in `_execute_node`!
        # Let's fix that in `engine.py` or just emit a special update dictionary.
        # Actually, if we return the full dict, we have to read it and update it.
        # But wait, this node runs in PARALLEL. We CANNOT safely read and write the whole dictionary!
        # Oh, in `engine.py`:
        # for field, new_val in worker_result.state_updates.items():
        #     if isinstance(new_val, dict) and isinstance(getattr(state, field), dict):
        #         getattr(state, field).update(new_val)
        #     else:
        #         setattr(state, field, new_val)
        # 
        # YES! The engine already supports merging dictionaries! 

        if section_result.success:
            content = section_result.data
        else:
            content = f"[Section writing failed: {section_result.error}]"

        result.success = True
        result.state_updates = {
            "report_sections": {self.section_name: content}
        }

        # We can optionally emit completion, but if multiple run in parallel, it might overlap.
        # We'll emit it anyway.
        result.add_event(
            "agent_status",
            agent="Section Writer",
            state="complete",
            statusText="Section written",
            subText=f"Completed {self.section_name}",
        )

        log.info("Section written: %s", self.section_name)
        return result
