"""
workers/planner.py — Planner Worker

Reads: query
Writes: plan (ResearchPlan with sub-tasks for parallel execution)
Tools: call_llm
"""

from __future__ import annotations

import json
import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from models.research import ResearchPlan, ResearchQuestion
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.planner import PLANNER_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.planner")


class PlannerWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "planner"

    @property
    def reads(self) -> list[str]:
        return ["query", "library_only", "library_papers"]

    @property
    def writes(self) -> list[str]:
        return ["plan"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        result.add_event(
            "agent_status",
            agent="Planner",
            state="working",
            statusText="Planning research...",
            subText="Defining scope & questions",
        )

        llm = tools.get("call_llm")
        provider = state.agent_providers.get("Planner", state.provider)
        temperature = state.agent_temperatures.get("Planner", 0.5)

        # Adjust prompt for library-only mode
        system_prompt = PLANNER_SYSTEM_PROMPT
        if state.library_only:
            paper_titles = [p.get("title", "Untitled") for p in state.library_papers]
            system_prompt += (
                "\n\nIMPORTANT: You are in LIBRARY-ONLY mode. "
                "Plan research using ONLY these library papers:\n"
                + "\n".join(f"- {t}" for t in paper_titles)
                + "\n\nDo NOT suggest searching for external sources. "
                "Your search_queries should be empty."
            )

        llm_result = await llm(
            system_prompt=system_prompt,
            user_input=json.dumps({"topic": state.query}),
            provider=provider,
            tier="fast",
            json_output=True,
            temperature=temperature,
        )

        if not llm_result.success:
            result.error = f"LLM call failed: {llm_result.error}"
            result.add_event(
                "agent_status",
                agent="Planner",
                state="failed",
                statusText="Planning failed",
                subText=result.error,
            )
            return result

        result.tokens_used = llm_result.metadata.get("tokens", 0)
        plan_data = parse_llm_json(llm_result.data)

        # Build structured plan
        questions = []
        for i, q in enumerate(plan_data.get("research_questions", [])):
            if isinstance(q, str):
                questions.append(ResearchQuestion(question=q, priority=len(plan_data.get("research_questions", [])) - i))
            elif isinstance(q, dict):
                questions.append(ResearchQuestion(
                    question=q.get("question", str(q)),
                    priority=q.get("priority", 0),
                ))

        plan = ResearchPlan(
            topic=plan_data.get("topic", state.query),
            goal=plan_data.get("goal", ""),
            research_questions=questions,
            search_queries=plan_data.get("search_queries", [state.query]),
            desired_sections=plan_data.get("desired_sections", [
                "Abstract", "Introduction", "Discussion", "Conclusion"
            ]),
            sub_tasks=plan_data.get("sub_tasks", plan_data.get("search_queries", [state.query])[:3]),
        )

        result.success = True
        result.state_updates = {"plan": plan}
        result.add_event(
            "agent_status",
            agent="Planner",
            state="complete",
            statusText="Plan Ready",
            subText=f"{len(questions)} questions, {len(plan.sub_tasks)} sub-tasks",
        )

        log.info(
            "Plan created: %d questions, %d sub-tasks, %d search queries",
            len(questions),
            len(plan.sub_tasks),
            len(plan.search_queries),
        )
        return result
