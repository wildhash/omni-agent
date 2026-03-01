"""Real-time vision analysis for OmniSight.

Supports Gemini Vision (preferred) and Claude Vision as fallback.
Falls back to a rule-based simulator when no API keys are present,
so the WebSocket still works for demo purposes.

Environment variables
---------------------
GEMINI_API_KEY   — Google Gemini API key (preferred)
ANTHROPIC_API_KEY — Anthropic Claude key (fallback)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are OmniSight, an expert UI/UX visual analyst.
Analyse this screenshot of a web application under development and return a JSON object
with EXACTLY this structure (no markdown, no explanation, just valid JSON):
{
  "elements": [
    {"type": "<button|input|nav|card|text|image|form|table>",
     "label": "<short description>",
     "bbox": [x1,y1,x2,y2],
     "issues": ["<short issue description or empty list>"],
     "confidence": 0.0-1.0}
  ],
  "issues": ["<WCAG or layout violations as plain strings>"],
  "insights": "<1-2 sentence summary for the developer>",
  "score": 0-100
}
bbox values are 0-1 ratios of the image (x1,y1 top-left; x2,y2 bottom-right).
Focus on: contrast, accessibility labels, alignment, overflow, responsive issues.
Return ONLY the JSON. No markdown fences."""


def _safe_json_from_model(raw: str) -> dict[str, Any] | None:
    content = raw.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(content[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _analysis_result_from_model_output(raw: str, *, latency_ms: float) -> AnalysisResult:
    data = _safe_json_from_model(raw)
    if data is None:
        return AnalysisResult(
            issues=["invalid model output"],
            insights="Model returned invalid JSON",
            score=0,
            latency_ms=latency_ms,
        )

    elements_raw = data.get("elements")
    issues_raw = data.get("issues")
    score_raw = data.get("score")

    elements: list[dict[str, Any]] = [
        el for el in elements_raw if isinstance(el, dict)
    ] if isinstance(elements_raw, list) else []
    issues: list[str] = (
        [str(i) for i in issues_raw if i is not None]
        if isinstance(issues_raw, list)
        else []
    )
    insights = data.get("insights") if isinstance(data.get("insights"), str) else ""
    score = int(score_raw) if isinstance(score_raw, (int, float)) else 0

    return AnalysisResult(
        elements=elements,
        issues=issues,
        insights=insights,
        score=score,
        latency_ms=latency_ms,
    )


@dataclass
class AnalysisResult:
    elements: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    insights: str = ""
    score: int = 0
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "elements": self.elements,
            "issues": self.issues,
            "insights": self.insights,
            "score": self.score,
            "latency_ms": self.latency_ms,
        }


class GeminiVisionAnalyser:
    def __init__(self) -> None:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self._model = genai.GenerativeModel("gemini-2.0-flash-exp")

    def analyse(self, jpeg_bytes: bytes) -> AnalysisResult:
        t0 = time.perf_counter()
        img_part = {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg_bytes).decode()}
        resp = self._model.generate_content([ANALYSIS_PROMPT, img_part])
        raw = resp.text.strip()
        latency = (time.perf_counter() - t0) * 1000
        return _analysis_result_from_model_output(raw, latency_ms=latency)


class ClaudeVisionAnalyser:
    def __init__(self) -> None:
        import anthropic  # type: ignore
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def analyse(self, jpeg_bytes: bytes) -> AnalysisResult:
        t0 = time.perf_counter()
        b64 = base64.b64encode(jpeg_bytes).decode()
        msg = self._client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": ANALYSIS_PROMPT},
                ],
            }],
        )
        raw = msg.content[0].text.strip()
        latency = (time.perf_counter() - t0) * 1000
        return _analysis_result_from_model_output(raw, latency_ms=latency)


class SimulatedAnalyser:
    """Deterministic simulator for demo/dev when no API keys are available."""

    _FRAMES = [
        AnalysisResult(
            elements=[
                {"type":"nav","label":"Navigation","bbox":[0.02,0.01,0.98,0.09],"issues":[],"confidence":0.95},
                {"type":"text","label":"Hero Heading","bbox":[0.08,0.13,0.92,0.27],"issues":[],"confidence":0.97},
            ],
            issues=[],
            insights="Header structure looks solid. Scanning for interactive elements…",
            score=68,
        ),
        AnalysisResult(
            elements=[
                {"type":"nav","label":"Navigation","bbox":[0.02,0.01,0.98,0.09],"issues":[],"confidence":0.95},
                {"type":"text","label":"Hero Heading","bbox":[0.08,0.13,0.92,0.27],"issues":[],"confidence":0.97},
                {"type":"button","label":"CTA Button","bbox":[0.34,0.40,0.66,0.50],"issues":["contrast:2.1:1"],"confidence":0.93},
                {"type":"input","label":"Email Field","bbox":[0.24,0.53,0.76,0.61],"issues":["no-aria-label"],"confidence":0.89},
            ],
            issues=[
                "Button contrast ratio 2.1:1 — fails WCAG AA (min 4.5:1)",
                "Email input missing accessible label",
            ],
            insights="2 accessibility violations. Sending report to coding agent.",
            score=51,
        ),
        AnalysisResult(
            elements=[
                {"type":"nav","label":"Navigation","bbox":[0.02,0.01,0.98,0.09],"issues":[],"confidence":0.96},
                {"type":"text","label":"Hero Heading","bbox":[0.08,0.13,0.92,0.27],"issues":[],"confidence":0.97},
                {"type":"button","label":"CTA Button","bbox":[0.34,0.40,0.66,0.50],"issues":[],"confidence":0.98},
                {"type":"input","label":"Email Field","bbox":[0.24,0.53,0.76,0.61],"issues":[],"confidence":0.96},
                {"type":"card","label":"Feature A","bbox":[0.02,0.66,0.32,0.84],"issues":[],"confidence":0.87},
                {"type":"card","label":"Feature B","bbox":[0.35,0.66,0.65,0.84],"issues":[],"confidence":0.87},
                {"type":"card","label":"Feature C","bbox":[0.68,0.66,0.98,0.84],"issues":[],"confidence":0.87},
            ],
            issues=[],
            insights="All violations resolved. 3-column grid detected. UI ready!",
            score=91,
        ),
    ]

    def __init__(self) -> None:
        self._idx = 0
        self._call = 0

    def analyse(self, _jpeg_bytes: bytes) -> AnalysisResult:
        self._call += 1
        # Cycle through frames slowly so the demo tells a story
        if self._call % 4 == 0:
            self._idx = min(self._idx + 1, len(self._FRAMES) - 1)
        result = deepcopy(self._FRAMES[self._idx])
        result.latency_ms = random.uniform(80, 200)
        return result


def build_analyser():
    """Return the best available analyser based on env vars."""
    if os.getenv("GEMINI_API_KEY"):
        try:
            analyser = GeminiVisionAnalyser()
            logger.info("OmniSight: using Gemini Vision")
            return analyser
        except Exception as exc:
            logger.warning("Gemini init failed: %s", exc)

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            analyser = ClaudeVisionAnalyser()
            logger.info("OmniSight: using Claude Vision")
            return analyser
        except Exception as exc:
            logger.warning("Claude init failed: %s", exc)

    logger.info("OmniSight: no API keys — using simulated analyser (demo mode)")
    return SimulatedAnalyser()
