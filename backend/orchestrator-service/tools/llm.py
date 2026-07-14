"""
tools/llm.py — Provider-agnostic LLM tool.

Wraps Gemini, OpenAI, and local LLaMA behind a single interface.
Every call is instrumented with token counting and timing.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .base import BaseTool, ToolResult

log = logging.getLogger("ars.tools.llm")


# ---------------------------------------------------------------------------
# Client singletons (lazy-initialized)
# ---------------------------------------------------------------------------
_gemini_client = None
_openai_client = None
_local_llama_client = None
_local_llama_available = False


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            _gemini_client = genai.Client(api_key=api_key)
        else:
            raise RuntimeError("Gemini API key not configured")
    return _gemini_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _openai_client = OpenAI(api_key=api_key)
        else:
            raise RuntimeError("OpenAI API key not configured")
    return _openai_client


def _get_local_llama_client():
    global _local_llama_client, _local_llama_available
    if _local_llama_client is None:
        from openai import OpenAI
        base_url = os.getenv("LOCAL_LLAMA_URL", "http://host.docker.internal:8080/v1")
        _local_llama_client = OpenAI(base_url=base_url, api_key="not-needed")
        _local_llama_available = True
    return _local_llama_client


# ---------------------------------------------------------------------------
# Model name maps
# ---------------------------------------------------------------------------
_MODEL_MAP = {
    "gemini": {"fast": "gemini-2.5-flash", "strong": "gemini-2.5-flash"},
    "openai": {"fast": "gpt-4o-mini", "strong": "gpt-4o"},
}


def _resolve_model(provider: str, tier: str) -> str:
    if provider == "local_llama":
        return os.getenv("LOCAL_LLAMA_MODEL", "local-model")
    return os.getenv(
        f"{provider.upper()}_{tier.upper()}_MODEL",
        _MODEL_MAP.get(provider, {}).get(tier, "gemini-2.5-flash"),
    )


# ---------------------------------------------------------------------------
# Provider dispatch functions
# ---------------------------------------------------------------------------
def _call_gemini(
    system_prompt: str,
    user_input: str,
    model: str,
    json_output: bool,
    temperature: float,
) -> str:
    from google.genai import types

    client = _get_gemini_client()
    config_kwargs = {"system_instruction": system_prompt, "temperature": temperature}
    if json_output:
        config_kwargs["response_mime_type"] = "application/json"

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_input)])],
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text


def _call_openai(
    system_prompt: str,
    user_input: str,
    model: str,
    json_output: bool,
    temperature: float,
) -> str:
    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if json_output:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_local_llama(
    system_prompt: str,
    user_input: str,
    model: str,
    json_output: bool,
    temperature: float,
) -> str:
    client = _get_local_llama_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if json_output:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------
class LLMTool(BaseTool):
    """Provider-agnostic LLM invocation tool."""

    @property
    def name(self) -> str:
        return "call_llm"

    @property
    def description(self) -> str:
        return "Call an LLM (Gemini, OpenAI, or local LLaMA) with a system prompt and user input."

    async def execute(
        self,
        system_prompt: str = "",
        user_input: str = "",
        provider: str = "gemini",
        tier: str = "fast",
        json_output: bool = False,
        temperature: float = 0.5,
        **kwargs,
    ) -> ToolResult:
        model = _resolve_model(provider, tier)

        dispatch = {
            "gemini": _call_gemini,
            "openai": _call_openai,
            "local_llama": _call_local_llama,
        }

        call_fn = dispatch.get(provider)
        if not call_fn:
            return ToolResult(success=False, error=f"Unknown provider: {provider}")

        try:
            raw = call_fn(system_prompt, user_input, model, json_output, temperature)
            return ToolResult(
                success=True,
                data=raw,
                metadata={"provider": provider, "model": model, "tier": tier},
            )
        except Exception as e:
            log.error("LLM call failed (%s/%s): %s", provider, model, e)
            return ToolResult(success=False, error=str(e))


def parse_llm_json(raw_text: str) -> dict:
    """Safely parse LLM JSON output, handling markdown fences and control chars."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned, strict=False)
    except Exception as e:
        log.warning("JSON parse error: %s", e)
        if '"report"' in cleaned:
            return {"report": cleaned}
        return {}
