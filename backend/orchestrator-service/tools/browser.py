"""
tools/browser.py — Playwright browser automation tool.

Provides low-level browser primitives (navigate, click, type, read)
as a callable tool.  Used by the KnowledgeCrawler agent.
"""

from __future__ import annotations

import asyncio
import base64
import re
import logging

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from .base import BaseTool, ToolResult

log = logging.getLogger("ars.tools.browser")


class BrowserSession:
    """
    Manages a Playwright browser session lifecycle.

    This is the same core as the original browser.py but cleaned up
    as a tool-friendly wrapper.
    """

    def __init__(self):
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        self.page = await self.context.new_page()
        log.info("Browser session started")

    async def stop(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        log.info("Browser session stopped")

    # ── Navigation ────────────────────────────────────────────────
    async def open_url(self, url: str) -> dict:
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)
            return {"success": True, "url": self.page.url, "title": await self.page.title()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def go_back(self) -> dict:
        try:
            await self.page.go_back(wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(1)
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Interaction ───────────────────────────────────────────────
    async def type_text(self, selector: str, text: str) -> dict:
        try:
            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.fill(selector, text)
            return {"success": True, "typed": text, "into": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str) -> dict:
        try:
            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            await asyncio.sleep(1)
            return {"success": True, "clicked": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def press_enter(self) -> dict:
        try:
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(1.5)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll_down(self) -> dict:
        try:
            await self.page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(0.5)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Reading ───────────────────────────────────────────────────
    async def read_page(self) -> dict:
        try:
            data = await self.page.evaluate("""
            () => {
                const url = document.location.href;
                const title = document.title;
                const body = document.body.innerText
                    .replace(/\\n{3,}/g, '\\n\\n')
                    .replace(/[ \\t]+/g, ' ')
                    .trim();
                return { url, title, text: body.substring(0, 4000) };
            }
            """)
            return {"success": True, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_arxiv_results(self) -> dict:
        """Extract structured results from an arXiv search results page."""
        try:
            results = await self.page.query_selector_all(".arxiv-result")
            if not results:
                return {"success": False, "error": "No .arxiv-result elements found"}

            papers = []
            for i, r in enumerate(results[:15]):
                try:
                    title_el = await r.query_selector("p.title")
                    title = (await title_el.inner_text()).strip() if title_el else None
                    if not title:
                        continue

                    author_els = await r.query_selector_all("p.authors a")
                    authors = [await a.inner_text() for a in author_els]

                    abstract_el = await r.query_selector("span.abstract-full")
                    if not abstract_el:
                        abstract_el = await r.query_selector("p.abstract")
                    abstract = ""
                    if abstract_el:
                        abstract = (await abstract_el.inner_text()).strip()
                        abstract = abstract.replace("Abstract:", "").replace("△ Less", "").strip()

                    pdf_el = await r.query_selector('a[href*="/pdf/"]')
                    pdf_url = await pdf_el.get_attribute("href") if pdf_el else None
                    if pdf_url and not pdf_url.startswith("http"):
                        pdf_url = f"https://arxiv.org{pdf_url}"

                    link_el = await r.query_selector('a[href*="/abs/"]')
                    paper_url = await link_el.get_attribute("href") if link_el else ""
                    arxiv_id = ""
                    if paper_url:
                        id_match = re.search(r'(\d{4}\.\d{4,5})', paper_url)
                        if id_match:
                            arxiv_id = id_match.group(1)

                    year = 0
                    meta_el = await r.query_selector("p.is-size-7")
                    if meta_el:
                        meta_text = await meta_el.inner_text()
                        year_match = re.search(r'(19|20)\d{2}', meta_text)
                        if year_match:
                            year = int(year_match.group())

                    papers.append({
                        "index": i,
                        "id": arxiv_id,
                        "title": title,
                        "authors": authors[:5],
                        "year": year,
                        "abstract": abstract[:800],
                        "pdfUrl": pdf_url,
                        "url": paper_url,
                        "venue": "arXiv",
                        "source": "Agent",
                    })
                except Exception:
                    continue

            return {"success": True, "count": len(papers), "papers": papers}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_arxiv_paper(self) -> dict:
        """Read an individual arXiv abstract page."""
        try:
            data = await self.page.evaluate("""
            () => {
                const title = document.querySelector('.title.mathjax');
                const authors = document.querySelector('.authors');
                const abstract = document.querySelector('.abstract.mathjax');
                const subjects = document.querySelector('.subjects');
                return {
                    url: document.location.href,
                    title: title ? title.innerText.replace('Title:', '').trim() : '',
                    authors: authors ? authors.innerText.replace('Authors:', '').trim() : '',
                    abstract: abstract ? abstract.innerText.replace('Abstract:', '').trim().substring(0, 1500) : '',
                    subjects: subjects ? subjects.innerText.trim() : '',
                };
            }
            """)
            return {"success": True, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Screenshots ───────────────────────────────────────────────
    async def get_screenshot(self) -> str | None:
        if not self.page:
            return None
        try:
            screenshot_bytes = await self.page.screenshot(type="jpeg", quality=50)
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception:
            return None


class BrowsePageTool(BaseTool):
    """Browse a URL and extract its text content."""

    @property
    def name(self) -> str:
        return "browse_page"

    @property
    def description(self) -> str:
        return "Navigate to a URL and read its content using a headless browser."

    async def execute(self, url: str = "", **kwargs) -> ToolResult:
        if not url:
            return ToolResult(success=False, error="URL is required")

        session = BrowserSession()
        await session.start()
        try:
            nav = await session.open_url(url)
            if not nav["success"]:
                return ToolResult(success=False, error=nav.get("error", "Navigation failed"))

            content = await session.read_page()
            return ToolResult(
                success=True,
                data={
                    "url": content.get("url", url),
                    "title": content.get("title", ""),
                    "text": content.get("text", ""),
                },
            )
        finally:
            await session.stop()
