"""WebAgent: real browser automation and web interactions via Playwright."""

from __future__ import annotations

import contextlib
from typing import Any, Dict, Iterator, Optional


class WebAgent:
    """Handles browser automation and web interactions using Playwright.

    - scrape / browse: navigate to URL and return real page text and title.
    - book flight: navigate to a flight-search URL and return page content (real scrape).
    """

    def __init__(self) -> None:
        self.tools = {
            "scrape": self._scrape,
            "book flight": self._book_flight,
        }

    @contextlib.contextmanager
    def _with_browser(self) -> Iterator[Any]:
        """Per-request browser (Gradio/thread-safe)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
            )
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                yield page
            finally:
                browser.close()
        finally:
            pw.stop()

    def execute(self, task: str, context: Optional[Dict] = None) -> Dict:
        context = context or {}
        task_lower = task.lower()

        if "scrape" in task_lower or "browse" in task_lower:
            return self._scrape(context.get("url", "https://example.com"))
        elif "flight" in task_lower or "book" in task_lower:
            return self._book_flight(context)
        else:
            return {"error": f"Web task not recognised: '{task}'"}

    def _scrape(self, url: str) -> Dict:
        """Fetch real page content from *url*."""
        if not url or not url.startswith(("http://", "https://")):
            url = "https://example.com" if not url else url
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
        try:
            with self._with_browser() as page:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(1500)
                title = page.title()
                content = page.evaluate("""() => document.body?.innerText ?? ''""")
                html_snippet = page.evaluate(
                    """() => document.body?.innerHTML?.slice(0, 5000) ?? ''"""
                )
            return {
                "status": "success",
                "url": url,
                "title": title,
                "content": (content or "").strip()[:15000],
                "html_snippet": (html_snippet or "").strip()[:5000],
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "url": url,
                "hint": "Check URL and network. Playwright must be installed with chromium.",
            }

    def _book_flight(self, context: Dict) -> Dict:
        """Navigate to a flight search page and return real content."""
        base_url = context.get(
            "url",
            "https://www.google.com/travel/flights",
        )
        from_airport = context.get("from", "SFO")
        to_airport = context.get("to", "NYC")
        date = context.get("date", "")
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url
        try:
            with self._with_browser() as page:
                page.goto(base_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2500)
                title = page.title()
                content = page.evaluate("""() => document.body?.innerText ?? ''""")
            return {
                "status": "success",
                "url": base_url,
                "title": title,
                "query": {"from": from_airport, "to": to_airport, "date": date},
                "content": (content or "").strip()[:15000],
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "url": base_url,
                "query": {"from": from_airport, "to": to_airport, "date": date},
                "hint": "Check URL and network.",
            }
