"""
workers/verification.py — Verification Worker

Reads: findings, evidence
Writes: verified_claims
Tools: call_llm, verify_citation

Implements evidence-first verification.
No claim enters the report without verification.
"""

from __future__ import annotations

import json
import logging

from .base import BaseWorker, WorkerResult
from models.task_state import TaskState
from models.verification import VerifiedClaim
from tools.registry import ToolRegistry
from tools.llm import parse_llm_json
from prompts.verification import VERIFICATION_SYSTEM_PROMPT

log = logging.getLogger("ars.workers.verification")


class VerificationWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "verification"

    @property
    def reads(self) -> list[str]:
        return ["findings", "evidence"]

    @property
    def writes(self) -> list[str]:
        return ["verified_claims"]

    async def execute(
        self,
        state: TaskState,
        tools: ToolRegistry,
    ) -> WorkerResult:
        result = WorkerResult(success=False)
        result.add_event(
            "agent_status",
            agent="Verification",
            state="working",
            statusText="Verifying claims...",
            subText=f"{len(state.findings)} claims to verify",
        )

        if not state.findings:
            result.success = True
            result.state_updates = {"verified_claims": []}
            result.add_event(
                "agent_status",
                agent="Verification",
                state="complete",
                statusText="No claims to verify",
                subText="0 findings",
            )
            return result

        # Build claims list for LLM verification
        claims_for_llm = []
        for f in state.findings:
            claims_for_llm.append({
                "claim": f.claim,
                "evidence": [
                    {
                        "text": e.text,
                        "source_id": e.source_id,
                        "source_title": e.source_title,
                    }
                    for e in f.supporting_evidence
                ],
                "source_ids": f.source_ids,
                "confidence": f.confidence,
            })

        llm = tools.get("call_llm")
        provider = state.agent_providers.get("Verification", state.provider)
        temperature = state.agent_temperatures.get("Verification", 0.3)

        llm_result = await llm(
            system_prompt=VERIFICATION_SYSTEM_PROMPT,
            user_input=json.dumps({"claims": claims_for_llm}),
            provider=provider,
            tier="fast",
            json_output=True,
            temperature=temperature,
        )

        if not llm_result.success:
            result.error = f"Verification LLM call failed: {llm_result.error}"
            return result

        verification_data = parse_llm_json(llm_result.data)

        # Build VerifiedClaim objects
        verified_claims = []
        for vc_data in verification_data.get("verified_claims", []):
            from models.research import Evidence

            evidences = []
            for e in vc_data.get("evidence", []):
                evidences.append(Evidence(
                    text=e.get("text", ""),
                    source_id=e.get("source_id", ""),
                    source_title=e.get("source_title", ""),
                ))

            claim = VerifiedClaim(
                claim=vc_data.get("claim", ""),
                evidence=evidences,
                source_ids=vc_data.get("source_ids", []),
                confidence=vc_data.get("confidence", 0.0),
                verification_method=vc_data.get("verification_method", "llm_check"),
                verified=vc_data.get("verified", False),
                rejection_reason=vc_data.get("rejection_reason", ""),
            )
            verified_claims.append(claim)

        # Also run heuristic citation verification on each claim
        if "verify_citation" in tools:
            citation_tool = tools.get("verify_citation")
            for vc in verified_claims:
                if vc.verified and vc.evidence:
                    cite_result = await citation_tool(
                        claim=vc.claim,
                        evidence_texts=[e.text for e in vc.evidence],
                        source_ids=vc.source_ids,
                    )
                    if cite_result.success:
                        heuristic_confidence = cite_result.data.get("confidence", 0)
                        # Blend LLM confidence with heuristic
                        vc.confidence = round(
                            (vc.confidence * 0.7 + heuristic_confidence * 0.3), 2
                        )
                    result.tool_calls.append({
                        "tool": "verify_citation",
                        "claim": vc.claim[:60],
                        "result": cite_result.data if cite_result.success else None,
                    })

        verified_count = sum(1 for vc in verified_claims if vc.verified)
        rejected_count = sum(1 for vc in verified_claims if not vc.verified)

        result.success = True
        result.state_updates = {"verified_claims": verified_claims}
        result.add_event(
            "agent_status",
            agent="Verification",
            state="complete",
            statusText=f"Verification complete",
            subText=f"{verified_count} verified, {rejected_count} rejected",
        )

        log.info(
            "Verification: %d verified, %d rejected out of %d",
            verified_count,
            rejected_count,
            len(verified_claims),
        )
        return result
