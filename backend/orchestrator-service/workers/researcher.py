"""
workers/researcher.py — Research Worker

Reads: plan, search_results, retrieved_chunks
Writes: findings, evidence, citations
Tools: retrieve_chunks, call_llm

The Research Worker does NOT search the web.
It retrieves knowledge from the vector store and synthesizes findings.
"""

from __future__ import annotations

import json
import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from models.research import Finding, Evidence, Citation
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.researcher import RESEARCHER_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.researcher")


class ResearcherWorker(BaseWorker):
    """
    Research worker for a single sub-task.

    The graph engine spawns one instance per sub-task from the plan.
    Each instance runs in parallel and writes to a partitioned slice
    of the findings list.
    """

    def __init__(self, sub_task: str = "", sub_task_index: int = 0):
        self.sub_task = sub_task
        self.sub_task_index = sub_task_index

    @property
    def name(self) -> str:
        return f"researcher_{self.sub_task_index}"

    @property
    def reads(self) -> list[str]:
        return ["plan", "search_results"]

    @property
    def writes(self) -> list[str]:
        return ["findings", "evidence", "citations"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        query = self.sub_task or state.query

        result.add_event(
            "agent_status",
            agent="Researcher",
            state="working",
            statusText=f"Researching: {query[:60]}...",
            subText=f"Sub-task {self.sub_task_index + 1}",
        )

        # Step 1: Retrieve relevant chunks from the knowledge base
        retrieval = tools.get("retrieve_chunks")
        retrieval_result = await retrieval(query=query, k=8)

        chunks = retrieval_result.data if retrieval_result.success else []
        result.tool_calls.append({
            "tool": "retrieve_chunks",
            "query": query,
            "results": len(chunks),
        })

        if not chunks and state.library_only:
            # In library-only mode with no chunks, build from library papers
            for lp in state.library_papers:
                chunks.append({
                    "paper_id": lp.get("id", ""),
                    "title": lp.get("title", ""),
                    "chunk": lp.get("abstract", "")[:500],
                    "similarity": 0.5,
                })

        # Step 2: Build context for LLM synthesis
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"[Chunk {i+1}] (Paper: {chunk.get('title', 'Unknown')}, "
                f"Relevance: {chunk.get('similarity', 0):.2f})\n"
                f"{chunk.get('chunk', '')}"
            )
        context = "\n\n---\n\n".join(context_parts) if context_parts else "No knowledge base context available."

        # Step 3: LLM synthesis
        llm = tools.get("call_llm")
        provider = state.agent_providers.get("Researcher", state.provider)
        temperature = state.agent_temperatures.get("Researcher", 0.5)

        questions = [q.question for q in (state.plan.research_questions if state.plan else [])]

        llm_input = (
            f"Research sub-task: {query}\n\n"
            f"Research questions to address:\n"
            + "\n".join(f"- {q}" for q in questions)
            + f"\n\n=== KNOWLEDGE BASE CONTEXT ===\n{context}"
        )

        llm_result = await llm(
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            user_input=llm_input,
            provider=provider,
            tier="fast",
            json_output=True,
            temperature=temperature,
        )

        if not llm_result.success:
            result.error = f"LLM synthesis failed: {llm_result.error}"
            return result

        research_data = parse_llm_json(llm_result.data)

        # Step 4: Build structured findings
        findings = []
        evidence_list = []
        citations = []

        for f_data in research_data.get("findings", []):
            # Build evidence objects
            evidences = []
            for e_data in f_data.get("supporting_evidence", []):
                ev = Evidence(
                    text=e_data.get("text", ""),
                    source_id=e_data.get("source_id", ""),
                    source_title=e_data.get("source_title", ""),
                )
                evidences.append(ev)
                evidence_list.append(ev)

            finding = Finding(
                claim=f_data.get("claim", ""),
                supporting_evidence=evidences,
                source_ids=f_data.get("source_ids", []),
                confidence=f_data.get("confidence", 0.0),
                sub_task=query,
                research_question=f_data.get("research_question", ""),
            )
            findings.append(finding)

        # Build citations from search results
        search_result_ids = set()
        for sr in state.search_results:
            search_result_ids.add(sr.arxiv_id or sr.url)
            citations.append(Citation(
                source_id=sr.arxiv_id or sr.url,
                title=sr.title,
                authors=sr.authors,
                year=sr.year,
                venue=sr.venue,
                url=sr.url,
                apa_text=(
                    f"{', '.join(sr.authors[:3])}, \"{sr.title},\" "
                    f"{sr.venue}, {sr.year}. {sr.url}"
                ),
            ))
            
        # Add citations for any sources the LLM referenced that aren't in search_results
        # (e.g. from internal knowledge or library papers)
        for ev in evidence_list:
            if ev.source_id and ev.source_id not in search_result_ids and ev.source_id != "model_knowledge":
                search_result_ids.add(ev.source_id)
                citations.append(Citation(
                    source_id=ev.source_id,
                    title=ev.source_title or ev.source_id,
                    authors=["Internal Knowledge"],
                    year=0,
                    venue="",
                    url="",
                    apa_text=f"Internal Knowledge, \"{ev.source_title or ev.source_id},\" n.d.",
                ))

        result.success = True
        result.state_updates = {
            "findings": findings,
            "evidence": evidence_list,
            "citations": citations,
        }
        result.add_event(
            "agent_status",
            agent="Researcher",
            state="complete",
            statusText=f"Research complete: {query[:40]}...",
            subText=f"{len(findings)} findings from {len(chunks)} chunks",
        )

        log.info(
            "Research complete: sub_task=%r, findings=%d, evidence=%d",
            query[:60],
            len(findings),
            len(evidence_list),
        )
        return result
