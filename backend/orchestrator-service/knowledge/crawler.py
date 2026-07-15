"""
knowledge/crawler.py — Knowledge Crawler Agent

An LLM-driven autonomous agent that searches arXiv and ingests papers
into the pgvector knowledge base.

This is the ONE component that retains agent-like behavior because
browser-based search genuinely requires dynamic decision-making.

The crawler is INDEPENDENT from report generation.
Research tasks consume knowledge — they do not build it.
"""

from __future__ import annotations

import json
import logging
import time
import re
from datetime import datetime
from dataclasses import dataclass, field

from tools.browser import BrowserSession
from tools.llm import LLMTool, parse_llm_json
from tools.ingestion import IngestionTool
from tools.memory import StoreMemoryTool, RecallMemoryTool

log = logging.getLogger("ars.knowledge.crawler")

MAX_AGENT_STEPS = 80
MIN_RELEVANT_PAPERS = 10
FINAL_SELECT_COUNT = 5

CRAWLER_SYSTEM_PROMPT = """\
You are an autonomous research agent browsing arXiv.org to find academic papers.
Your overarching research objective is: "{query}"

## CORE DIRECTIVES (PREVENT SEMANTIC DRIFT)
1. You MUST stay semantically aligned with your overarching research objective.
2. It is OK to explore synonyms and related terminology, but do NOT drift into unrelated domains.
3. If search results are poor, reformulate your query but remain focused on the primary objective.
4. Search queries must be validated against the overarching goal before typing.

## MANDATORY WORKFLOW (Follow these exact JSON actions)
1. You are already on the search page. Type search: {"action": "type", "selector": "#query", "text": "your search term"}
2. Get results: {"action": "read_results"}
3. Open a paper: {"action": "open_paper", "index": 0}
4. Read abstract: {"action": "read_paper"}
5. Decide: {"action": "select_paper", "index": 0, "reason": "why"} OR {"action": "reject_paper", "index": 0, "reason": "why"}
6. Go back: {"action": "go_back"}
7. Repeat steps 3-6 for index 1, 2, 3, etc.
8. Finish when you have at least 10 papers: {"action": "done", "summary": "Finished"}

## Available actions (reply with ONLY ONE JSON object per turn)
| Action | JSON |
|--------|------|
| Navigate | {"action": "open_url", "url": "..."} |
| Type & Submit | {"action": "type", "selector": "...", "text": "..."} |
| Click | {"action": "click", "selector": "..."} |
| Go back | {"action": "go_back"} |
| Scroll down | {"action": "scroll_down"} |
| Read page | {"action": "read_page"} |
| Read results | {"action": "read_results"} |
| Read paper | {"action": "read_paper"} |
| Open paper | {"action": "open_paper", "index": 0} |
| Select paper | {"action": "select_paper", "index": 0, "reason": "..."} |
| Reject paper | {"action": "reject_paper", "index": 0, "reason": "..."} |
| Next page | {"action": "next_page"} |
| Done | {"action": "done", "summary": "..."} |

## Rules
- Reply with ONLY the JSON action, nothing else. No markdown, no conversational text.
- Use the selector "#query" for typing the search.
- You must read each paper's abstract before selecting it.
- Collect at least 10 relevant papers.
"""


@dataclass
class CrawlResult:
    """Result of a crawl session."""
    papers: list[dict] = field(default_factory=list)
    total_found: int = 0
    ingestion_results: list[dict] = field(default_factory=list)
    duration_seconds: float = 0
    steps_taken: int = 0


class KnowledgeCrawler:
    """
    Autonomous arXiv search agent.

    Writes ONLY to the knowledge base (paper_chunks table).
    Does NOT write to TaskState.
    """

    def __init__(self, llm_tool: LLMTool | None = None):
        self.llm = llm_tool or LLMTool()
        self.ingestion = IngestionTool()

    async def crawl(
        self,
        queries: list[str],
        sse_callback=None,
    ) -> CrawlResult:
        """
        Run the browser agent to find and ingest papers.

        Args:
            queries: Search queries to execute
            sse_callback: Optional async function to send SSE events
        """
        result = CrawlResult()
        start = time.time()

        for query in queries:
            papers = await self._search_arxiv(query, sse_callback)
            result.papers.extend(papers)

        # Deduplicate by title
        seen = set()
        unique = []
        for p in result.papers:
            t = p.get("title", "").strip().lower()
            if t and t not in seen:
                seen.add(t)
                unique.append(p)
        result.papers = unique
        result.total_found = len(unique)

        # Rank and select top papers
        if len(unique) > FINAL_SELECT_COUNT:
            unique = unique[:FINAL_SELECT_COUNT]

        # Ingest papers into knowledge base
        for paper in unique:
            try:
                ingest_result = await self.ingestion(
                    title=paper.get("title", "Unknown"),
                    pdf_url=paper.get("pdfUrl", ""),
                    paper_id=paper.get("id", ""),
                    arxiv_id=paper.get("id", ""),
                    venue=paper.get("venue", "arXiv"),
                )
                result.ingestion_results.append(ingest_result.data if ingest_result.success else {"error": ingest_result.error})
            except Exception as e:
                log.error("Ingestion failed for %r: %s", paper.get("title", ""), e)

        result.duration_seconds = time.time() - start
        log.info(
            "Crawl complete: %d papers found, %d ingested in %.0fs",
            result.total_found,
            len(result.ingestion_results),
            result.duration_seconds,
        )
        return result

    async def _search_arxiv(self, query: str, sse_callback=None) -> list[dict]:
        """Run the LLM-driven browser agent for a single query."""
        browser = BrowserSession()
        selected_papers = []
        all_results_cache = []
        reviewed_indices = set()

        await browser.start()
        try:
            # Initial navigation
            await browser.open_url("https://arxiv.org/search/")

            system_prompt_formatted = CRAWLER_SYSTEM_PROMPT.replace("{query}", query)
            conversation = [
                {"role": "system", "content": system_prompt_formatted},
                {"role": "user", "content": (
                    f'Find academic papers about: "{query}"\n'
                    f'You are already on https://arxiv.org/search/.\n'
                    f'Start by typing your search query into "#query" and pressing enter.'
                )},
            ]

            for step in range(MAX_AGENT_STEPS):
                if sse_callback:
                    await sse_callback(json.dumps({
                        "type": "agent_step",
                        "step": step + 1,
                        "message": "Analyzing page...",
                        "status": "running"
                    }))

                # Build context window to prevent semantic drift
                if len(conversation) > 8:
                    recent_history = conversation[1:2] + conversation[-6:]
                else:
                    recent_history = conversation[1:]

                history_blocks = []
                for msg in recent_history:
                    role = msg["role"].upper()
                    history_blocks.append(f"{role}:\n{msg['content']}")
                
                user_input = "\n\n---\n\n".join(history_blocks)

                llm_result = await self.llm(
                    system_prompt=system_prompt_formatted,
                    user_input=user_input,
                    provider="local_llama",
                    tier="fast",
                    json_output=True,
                    temperature=0.4,
                )

                if not llm_result.success or not llm_result.data:
                    if sse_callback:
                        await sse_callback(json.dumps({
                            "type": "agent_step",
                            "step": step + 1,
                            "message": f"LLM Error: {llm_result.error}",
                            "status": "error"
                        }))
                    continue

                # Parse action
                try:
                    action = parse_llm_json(llm_result.data)
                except Exception:
                    action = None

                if not action:
                    if sse_callback:
                        await sse_callback(json.dumps({
                            "type": "agent_step",
                            "step": step + 1,
                            "message": "Failed to parse LLM response. Retrying...",
                            "status": "error",
                            "reasoning": llm_result.data[:100]
                        }))
                    continue

                action_type = action.get("action", "")
                conversation.append({"role": "assistant", "content": json.dumps(action)})
                observation = ""

                # Emit SSE for frontend
                if sse_callback:
                    import base64
                    screenshot_b64 = None
                    if browser.page:
                        try:
                            # 30% quality JPEG is enough for the UI to show what's happening
                            img_bytes = await browser.page.screenshot(type="jpeg", quality=30)
                            screenshot_b64 = f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode()}"
                        except Exception:
                            pass
                    
                    step_event = {
                        "type": "agent_step",
                        "step": step + 1,
                        "message": f"Action: {action_type.replace('_', ' ').capitalize()}",
                        "status": "running",
                        "reasoning": json.dumps(action),
                        "screenshot": screenshot_b64
                    }
                    await sse_callback(json.dumps(step_event))

                # Execute action (simplified — mirrors original agent.py logic)
                if action_type == "done":
                    if len(selected_papers) >= MIN_RELEVANT_PAPERS:
                        break
                    observation = f"Only {len(selected_papers)} papers. Need {MIN_RELEVANT_PAPERS}. Keep searching."

                elif action_type == "type":
                    selector = action.get("selector", "")
                    text = action.get("text", "")
                    result = await browser.type_text(selector, text)
                    if browser.page and selector:
                        try:
                            await browser.page.press(selector, "Enter")
                            import asyncio
                            await asyncio.sleep(2)
                        except:
                            pass
                    observation = f"Typed '{text}' and pressed Enter. Use read_results."

                elif action_type == "click":
                    result = await browser.click(action.get("selector", ""))
                    observation = "Clicked. Use read_results to see results."

                elif action_type == "read_results":
                    result = await browser.read_arxiv_results()
                    if result["success"]:
                        all_results_cache = result.get("papers", [])
                        summaries = [f"[{p['index']}] \"{p['title']}\"" for p in all_results_cache]
                        observation = f"Found {len(all_results_cache)} papers:\n" + "\n".join(summaries)
                    else:
                        observation = "No results found."

                elif action_type == "open_paper":
                    idx = action.get("index", -1)
                    if 0 <= idx < len(all_results_cache):
                        paper = all_results_cache[idx]
                        url = paper.get("url", "")
                        if url and not url.startswith("http"):
                            url = f"https://arxiv.org{url}"
                        await browser.open_url(url)
                        observation = f"Opened [{idx}]. Use read_paper to read abstract."

                elif action_type == "read_paper":
                    result = await browser.read_arxiv_paper()
                    if result["success"]:
                        reviewed_indices.add(action.get("index", -1))
                        observation = f"Title: {result.get('title', '')}\nAbstract: {result.get('abstract', '')}"

                elif action_type == "select_paper":
                    idx = action.get("index", -1)
                    if 0 <= idx < len(all_results_cache):
                        selected_papers.append(all_results_cache[idx])
                        observation = f"Selected. Have {len(selected_papers)}/{MIN_RELEVANT_PAPERS}."

                elif action_type == "reject_paper":
                    observation = "Rejected. go_back and try next paper."

                elif action_type == "go_back":
                    await browser.go_back()
                    observation = "Back to results. Open next un-reviewed paper."

                elif action_type == "next_page":
                    await browser.click("a.pagination-next")
                    observation = "Next page. Use read_results."

                elif action_type == "open_url":
                    await browser.open_url(action.get("url", ""))
                    observation = f"Page loaded: {browser.page.url if browser.page else action.get('url')}"

                elif action_type == "scroll_down":
                    await browser.scroll_down()
                    observation = "Scrolled down."

                if observation:
                    conversation.append({"role": "user", "content": observation})

                # Keep conversation manageable
                if len(conversation) > 16:
                    conversation = [conversation[0]] + conversation[-14:]

                if len(selected_papers) >= 15:
                    break

        except Exception as e:
            log.exception("Crawler crashed: %s", e)
        finally:
            await browser.stop()

        return selected_papers
