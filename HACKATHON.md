# OmniSight — Visual Dev Agent
### WeMakeDevs VisionPossible Hackathon Entry

> **"AI coding agents are code-blind. They write code but can't see if the UI looks right. OmniSight closes the loop."**

---

## The Problem

Cursor, GitHub Copilot, VS Code AI — they all write code. But they're **visually blind**. They can't see:
- Whether the button contrast fails WCAG
- Whether the layout breaks on mobile
- Whether the UI actually matches the design intent

The coding agent has to _guess_ from the code alone whether the visual output is correct.

## The Solution

OmniSight is a **real-time vision agent** that watches the UI as it's built:

1. **Captures** the browser preview via screen share (WebRTC / `getDisplayMedia`)
2. **Streams** frames to a vision analysis pipeline (Gemini Vision / Claude Vision)
3. **Detects** UI elements, accessibility violations, layout issues in real-time
4. **Scores** the UI quality (0–100) and reports violations back to the coding agent

The coding agent now has **eyes**. It closes the visual feedback loop.

## Architecture

```
Browser (React + Vite)
  ├── Screen Capture (getDisplayMedia → canvas → JPEG)
  ├── WebSocket client → ws://backend:8000/ws/vision
  └── Overlay canvas (bounding boxes + labels from analysis)

FastAPI Backend (extends omni-agent)
  ├── /ws/vision  WebSocket — receives frames, returns analysis JSON
  ├── GeminiVisionAnalyser   (GEMINI_API_KEY)
  ├── ClaudeVisionAnalyser   (ANTHROPIC_API_KEY)
  └── SimulatedAnalyser      (no key needed — demo mode)

Vision AI → Structured JSON
  {"elements": [...], "issues": [...], "insights": "...", "score": 0-100}
```

## Quick Start

### Frontend
```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

### Backend
```bash
pip install -r requirements-vision.txt

# Optional: set one or both keys for real vision analysis
export GEMINI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export OMNI_AGENT_ALLOW_INSECURE_NOAUTH=1

python -m omni_agent.backend.main
# → ws://localhost:8000/ws/vision
```

### Demo (no backend needed)
Open the frontend and click **◉ Run Demo** — scripted analysis plays automatically.

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18, Vite, TypeScript, Canvas API |
| Streaming | WebSocket (`getDisplayMedia` → JPEG → WS) |
| Vision AI | Gemini 2.0 Flash / Claude Opus 4.6 |
| Backend | FastAPI (extends omni-agent) |
| Overlay | HTML5 Canvas (bounding boxes, corner marks) |

## Hackathon Alignment

| Requirement | How we meet it |
|-------------|----------------|
| Multi-modal AI agents | Vision agent + LLM agent combined |
| Watch video in real-time | Screen capture streamed at 2fps |
| <30ms A/V latency | WebSocket + canvas pipeline |
| Real-world use case | Dev tooling — every frontend developer |
| Native LLM APIs | Gemini 2.0 Flash + Claude claude-opus-4-6 direct APIs |

## What's Next (VS Code Integration)

The next layer is a VS Code extension ([wildhash/vscode](https://github.com/wildhash/vscode)) that:
- Watches the Simple Browser / WebView panel directly (no screen share needed)
- Shows analysis as inline editor decorations
- Gives the AI coding agent visual awareness _natively_ in the editor

This is the **first AI coding assistant that can see what it builds**.
