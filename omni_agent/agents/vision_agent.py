"""VisionAgent: browser-based visual inspection and frontend development feedback.

Uses Playwright to capture screenshots, extract DOM structure, and provide
a visual feedback loop for iterating on UI changes in real time.
"""

from __future__ import annotations

import base64
import contextlib
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


class VisionAgent:
    """Capture, inspect, and analyse frontend UIs via headless browser.

    Supported tasks
    ---------------
    - screenshot / capture: take a PNG screenshot of a URL
    - analyze / inspect: screenshot + DOM structure extraction
    - diff: compare two screenshots to detect visual changes
    - elements: list interactive elements on the page

    Uses a fresh Playwright browser per request so it is safe when called
    from multi-threaded contexts (e.g. Gradio).
    """

    def __init__(self) -> None:
        self.tools: Dict[str, Any] = {
            "screenshot": self._screenshot,
            "analyze": self._analyze,
            "diff": self._diff,
            "elements": self._list_elements,
        }

    @contextlib.contextmanager
    def _with_browser(self, viewport: Optional[Dict[str, int]] = None) -> Iterator[Any]:
        """Context: start Playwright, yield a new page, then tear down.
        Ensures each request uses its own thread-local browser (Gradio-safe).
        """
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
                vp = viewport or {"width": 1280, "height": 900}
                page = browser.new_page(viewport=vp)
                yield page
            finally:
                browser.close()
        finally:
            pw.stop()

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        task_lower = task.lower()

        if any(kw in task_lower for kw in ("screenshot", "capture", "snap")):
            return self._screenshot(context)
        elif any(kw in task_lower for kw in ("analyze", "analyse", "inspect", "review")):
            return self._analyze(context)
        elif "diff" in task_lower or "compare" in task_lower:
            return self._diff(context)
        elif "element" in task_lower or "interactive" in task_lower:
            return self._list_elements(context)
        elif any(kw in task_lower for kw in ("vision", "see", "look", "view")):
            return self._analyze(context)
        else:
            return {
                "error": f"Vision task not recognised: '{task}'",
                "hint": "Try: screenshot, analyze, diff, or elements.",
            }

    def _screenshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate to a URL and return a base64-encoded PNG screenshot."""
        url = context.get("url", "http://127.0.0.1:7860")
        wait_ms = int(context.get("wait_ms", 2000))
        selector = context.get("wait_for")

        try:
            with self._with_browser(context.get("viewport")) as page:
                page.goto(url, wait_until="networkidle", timeout=15000)
                if selector:
                    page.wait_for_selector(selector, timeout=5000)
                else:
                    page.wait_for_timeout(wait_ms)

                png_bytes = page.screenshot(full_page=context.get("full_page", True))
                title = page.title()
                current_url = page.url

                save_path = context.get("save_path")
                if save_path:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(save_path).write_bytes(png_bytes)

                return {
                    "status": "success",
                    "url": current_url,
                    "title": title,
                    "image_base64": base64.b64encode(png_bytes).decode("ascii"),
                    "image_size_bytes": len(png_bytes),
                    "content_type": "image/png",
                }
        except Exception as exc:
            return {"error": str(exc), "hint": f"Failed to capture {url}"}

    def _analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Screenshot + DOM structure extraction for a URL."""
        url = context.get("url", "http://127.0.0.1:7860")
        wait_ms = int(context.get("wait_ms", 2000))

        try:
            with self._with_browser(context.get("viewport")) as page:
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(wait_ms)

                png_bytes = page.screenshot(full_page=context.get("full_page", True))
                title = page.title()

                dom_summary = page.evaluate("""() => {
                function walk(el, depth) {
                    if (depth > 4) return null;
                    const tag = el.tagName?.toLowerCase() || '';
                    const id = el.id ? '#' + el.id : '';
                    const cls = el.className && typeof el.className === 'string'
                        ? '.' + el.className.trim().split(/\\s+/).join('.')
                        : '';
                    const text = el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
                        ? el.childNodes[0].textContent?.trim().slice(0, 80) || ''
                        : '';
                    const children = [];
                    for (const child of el.children || []) {
                        const c = walk(child, depth + 1);
                        if (c) children.push(c);
                    }
                    return {
                        tag: tag + id + cls,
                        text: text || undefined,
                        children: children.length ? children : undefined
                    };
                }
                return walk(document.body, 0);
            }""")

                interactive = page.evaluate("""() => {
                    const items = [];
                    document.querySelectorAll(
                        'button, input, textarea, select, a[href], [role="button"], [role="tab"]'
                    ).forEach(el => {
                        items.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || undefined,
                            text: (el.textContent || '').trim().slice(0, 100),
                            id: el.id || undefined,
                            name: el.name || undefined,
                            placeholder: el.placeholder || undefined,
                            role: el.getAttribute('role') || undefined,
                            visible: el.offsetParent !== null,
                        });
                    });
                    return items;
                }""")

                viewport_info = page.evaluate("""() => ({
                    width: window.innerWidth,
                    height: window.innerHeight,
                    scrollHeight: document.body.scrollHeight,
                    title: document.title,
                })""")

                save_path = context.get("save_path")
                if save_path:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(save_path).write_bytes(png_bytes)

                return {
                    "status": "success",
                    "url": url,
                    "title": title,
                    "viewport": viewport_info,
                    "image_base64": base64.b64encode(png_bytes).decode("ascii"),
                    "image_size_bytes": len(png_bytes),
                    "content_type": "image/png",
                    "dom_summary": dom_summary,
                    "interactive_elements": interactive,
                    "element_count": len(interactive),
                }
        except Exception as exc:
            return {"error": str(exc), "hint": f"Failed to analyze {url}"}

    def _diff(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Take two screenshots (before/after) and report size delta."""
        url = context.get("url", "http://127.0.0.1:7860")
        delay_s = float(context.get("delay_s", 3))

        try:
            with self._with_browser(context.get("viewport")) as page:
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(1500)
                before = page.screenshot(full_page=True)

                page.wait_for_timeout(int(delay_s * 1000))
                after = page.screenshot(full_page=True)

                pixels_changed = self._compare_pngs(before, after)

                return {
                    "status": "success",
                    "url": url,
                    "before_size_bytes": len(before),
                    "after_size_bytes": len(after),
                    "before_base64": base64.b64encode(before).decode("ascii"),
                    "after_base64": base64.b64encode(after).decode("ascii"),
                    "pixels_changed": pixels_changed,
                    "content_type": "image/png",
                }
        except Exception as exc:
            return {"error": str(exc)}

    def _list_elements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return all interactive elements on the page."""
        url = context.get("url", "http://127.0.0.1:7860")

        try:
            with self._with_browser(context.get("viewport")) as page:
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(1500)

                elements = page.evaluate("""() => {
                    const items = [];
                    document.querySelectorAll(
                        'button, input, textarea, select, a[href], [role="button"], [role="tab"], [role="tabpanel"]'
                    ).forEach(el => {
                        const rect = el.getBoundingClientRect();
                        items.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || undefined,
                            text: (el.textContent || '').trim().slice(0, 120),
                            id: el.id || undefined,
                            placeholder: el.placeholder || undefined,
                            role: el.getAttribute('role') || undefined,
                            visible: el.offsetParent !== null,
                            bounds: { x: Math.round(rect.x), y: Math.round(rect.y),
                                      w: Math.round(rect.width), h: Math.round(rect.height) },
                        });
                    });
                    return items;
                }""")

                return {
                    "status": "success",
                    "url": url,
                    "elements": elements,
                    "count": len(elements),
                }
        except Exception as exc:
            return {"error": str(exc)}

    @staticmethod
    def _compare_pngs(a: bytes, b: bytes) -> int:
        """Byte-level comparison returning a rough change metric."""
        try:
            from PIL import Image
            import io as _io

            img_a = Image.open(_io.BytesIO(a)).convert("RGB")
            img_b = Image.open(_io.BytesIO(b)).convert("RGB")
            if img_a.size != img_b.size:
                return -1
            pix_a = img_a.load()
            pix_b = img_b.load()
            changed = 0
            w, h = img_a.size
            step = max(1, (w * h) // 10000)
            for i in range(0, w * h, step):
                x, y = i % w, i // w
                if y < h and pix_a[x, y] != pix_b[x, y]:
                    changed += 1
            return changed * step
        except ImportError:
            return -1 if a != b else 0
