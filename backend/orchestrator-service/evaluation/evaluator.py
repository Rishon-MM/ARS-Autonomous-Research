"""
evaluation/evaluator.py — Task evaluation metrics computation.

Computes quantitative metrics for every completed research task.
Results are stored in the evaluations table for trend analysis.
"""

from __future__ import annotations

import logging
from state.state_manager import StateManager
from models.task_state import TaskState
from models.evaluation import EvaluationMetrics

log = logging.getLogger("ars.evaluation")


class TaskEvaluator:
    """Compute evaluation metrics from a completed TaskState."""

    def __init__(self, state_manager: StateManager):
        self.sm = state_manager

    async def evaluate(self, state: TaskState) -> EvaluationMetrics:
        """Compute and persist evaluation metrics."""
        total_claims = len(state.findings)
        verified = sum(1 for vc in state.verified_claims if vc.verified)
        rejected = sum(1 for vc in state.verified_claims if not vc.verified)

        questions_total = len(state.plan.research_questions) if state.plan else 0
        questions_answered = sum(
            1 for q in (state.plan.research_questions if state.plan else [])
            if q.answered
        )

        total_tokens = sum(e.tokens_used for e in state.execution_log)
        total_tool_calls = sum(
            1 for e in state.execution_log
            if "tool" in e.event_type.value
        )
        total_llm_calls = sum(
            1 for e in state.execution_log
            if e.tool_name == "call_llm"
        )

        latency = 0.0
        if state.started_at and state.completed_at:
            latency = (state.completed_at - state.started_at).total_seconds()

        metrics = EvaluationMetrics(
            task_success=1.0 if state.final_report and verified > 0 else 0.0,
            citation_accuracy=verified / max(total_claims, 1),
            source_coverage=min(
                len(state.citations) / max(len(state.search_results), 1), 1.0
            ),
            verification_rate=verified / max(total_claims, 1),
            tool_efficiency=(
                total_tool_calls / max(total_llm_calls + total_tool_calls, 1)
            ),
            latency=latency,
            cost=total_tokens * 0.000001,
            research_completeness=questions_answered / max(questions_total, 1),
            total_tokens_used=total_tokens,
            total_tool_calls=total_tool_calls,
            total_llm_calls=total_llm_calls,
            total_retrieval_calls=sum(
                1 for e in state.execution_log
                if e.tool_name == "retrieve_chunks"
            ),
            total_claims=total_claims,
            verified_claims=verified,
            rejected_claims=rejected,
        )

        # Persist
        await self.sm.save_evaluation(state.task_id, metrics.model_dump())
        log.info(
            "Evaluation: task=%s success=%.1f verification=%.1f latency=%.0fs",
            state.task_id,
            metrics.task_success,
            metrics.verification_rate,
            metrics.latency,
        )
        return metrics
