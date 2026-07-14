"""
workers/reflection.py — Reflection Worker

Reads: final_report, verified_claims, execution_log, metrics
Writes: reflection, metrics
Tools: call_llm, store_memory

Produces structured reflection and evaluation metrics that
feed back into future planning.
"""

from __future__ import annotations

import json
import logging
import time

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from models.evaluation import EvaluationMetrics, ReflectionRecord
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.reflection import REFLECTION_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.reflection")


class ReflectionWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "reflection"

    @property
    def reads(self) -> list[str]:
        return ["query", "plan", "findings", "verified_claims", "final_report", "execution_log"]

    @property
    def writes(self) -> list[str]:
        return ["reflection", "metrics"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        result.add_event(
            "agent_status",
            agent="Reflection",
            state="working",
            statusText="Evaluating & reflecting...",
            subText="Computing metrics",
        )

        # ── Step 1: Compute quantitative metrics ──────────────────
        total_claims = len(state.findings)
        verified = sum(1 for vc in state.verified_claims if vc.verified)
        rejected = sum(1 for vc in state.verified_claims if not vc.verified)
        questions_total = len(state.plan.research_questions) if state.plan else 0
        questions_answered = sum(
            1 for q in (state.plan.research_questions if state.plan else [])
            if q.answered
        )

        # Calculate tool call stats from execution log
        total_tool_calls = sum(
            1 for e in state.execution_log
            if e.event_type.value in ("tool_called", "tool_completed")
        )
        total_tokens = sum(e.tokens_used for e in state.execution_log)

        # Timing
        latency = 0.0
        if state.started_at:
            latency = (state.updated_at - state.started_at).total_seconds()

        metrics = EvaluationMetrics(
            task_success=1.0 if state.final_report and verified > 0 else 0.5,
            citation_accuracy=verified / max(total_claims, 1),
            source_coverage=min(len(state.citations) / max(len(state.search_results), 1), 1.0),
            verification_rate=verified / max(total_claims, 1),
            tool_efficiency=0.8,  # placeholder — refined with real tool stats
            latency=latency,
            cost=total_tokens * 0.000001,  # rough estimate
            research_completeness=questions_answered / max(questions_total, 1),
            total_tokens_used=total_tokens,
            total_tool_calls=total_tool_calls,
            total_llm_calls=sum(
                1 for e in state.execution_log
                if e.tool_name == "call_llm"
            ),
            total_retrieval_calls=sum(
                1 for e in state.execution_log
                if e.tool_name == "retrieve_chunks"
            ),
            total_claims=total_claims,
            verified_claims=verified,
            rejected_claims=rejected,
        )

        # ── Step 2: LLM-generated reflection ─────────────────────
        llm = tools.get("call_llm")
        provider = state.agent_providers.get("Reflection", state.provider)
        temperature = state.agent_temperatures.get("Reflection", 0.4)

        reflection_input = json.dumps({
            "query": state.query,
            "plan_goal": state.plan.goal if state.plan else "",
            "questions": [q.question for q in (state.plan.research_questions if state.plan else [])],
            "findings_count": total_claims,
            "verified_count": verified,
            "rejected_count": rejected,
            "report_length": len(state.final_report),
            "latency_seconds": latency,
            "total_tokens": total_tokens,
            "metrics": {
                "citation_accuracy": metrics.citation_accuracy,
                "verification_rate": metrics.verification_rate,
                "source_coverage": metrics.source_coverage,
            },
        })

        llm_result = await llm(
            system_prompt=REFLECTION_SYSTEM_PROMPT,
            user_input=reflection_input,
            provider=provider,
            tier="fast",
            json_output=True,
            temperature=temperature,
        )

        reflection = ReflectionRecord()
        if llm_result.success:
            reflection_data = parse_llm_json(llm_result.data)
            reflection = ReflectionRecord(
                outcome_type=reflection_data.get("outcome_type", "mixed"),
                confidence=reflection_data.get("confidence", 0.5),
                successful_strategies=reflection_data.get("successful_strategies", []),
                failed_strategies=reflection_data.get("failed_strategies", []),
                retrieval_quality=reflection_data.get("retrieval_quality", {}),
                verification_outcomes=reflection_data.get("verification_outcomes", {}),
                planning_feedback=reflection_data.get("planning_feedback", ""),
                query_refinement_suggestions=reflection_data.get("query_refinement_suggestions", []),
            )

        # ── Step 3: Store in memory for future tasks ──────────────
        if "store_memory" in tools:
            memory_tool = tools.get("store_memory")
            lesson_parts = []
            if reflection.successful_strategies:
                lesson_parts.append("Worked: " + "; ".join(reflection.successful_strategies[:3]))
            if reflection.planning_feedback:
                lesson_parts.append(reflection.planning_feedback)
            lesson = " | ".join(lesson_parts) if lesson_parts else f"Research on '{state.query}' completed"

            anti_pattern = ""
            if reflection.failed_strategies:
                anti_pattern = "; ".join(reflection.failed_strategies[:3])

            await memory_tool(
                query=state.query,
                lesson=lesson,
                outcome_type=reflection.outcome_type,
                confidence=reflection.confidence,
                anti_pattern=anti_pattern,
                action="graph_research",
                result_summary=f"{verified}/{total_claims} claims verified, {len(state.final_report)} chars report",
            )
            result.tool_calls.append({"tool": "store_memory", "lesson": lesson[:100]})

        # Update task success based on reflection
        metrics.task_success = reflection.confidence

        result.success = True
        result.state_updates = {
            "reflection": reflection,
            "metrics": metrics,
        }
        result.add_event(
            "agent_status",
            agent="Reflection",
            state="complete",
            statusText=f"Evaluation: {reflection.outcome_type}",
            subText=(
                f"Confidence: {reflection.confidence:.0%} | "
                f"Verified: {verified}/{total_claims} | "
                f"Latency: {latency:.0f}s"
            ),
        )

        log.info(
            "Reflection: outcome=%s, confidence=%.2f, verified=%d/%d",
            reflection.outcome_type,
            reflection.confidence,
            verified,
            total_claims,
        )
        return result
