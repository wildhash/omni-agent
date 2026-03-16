#!/usr/bin/env python3
"""Capture the local frontend and write to .omni-agent/ so the AI can see it.

Run from project root (or set FRONTEND_URL). The AI can then read:
  .omni-agent/screenshot.png
  .omni-agent/frontend-summary.txt

Usage:
  python scripts/capture_for_ai.py
  python scripts/capture_for_ai.py --url http://127.0.0.1:7860
"""

import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()

from omni_agent.orchestrator import AgentOrchestrator


def main():
    url = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000")
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--url" and i + 1 < len(args):
            url = args[i + 1]
            break

    snapshot_dir = Path(os.getenv("OMNI_AGENT_SNAPSHOT_DIR", ".omni-agent"))
    snapshot_dir = snapshot_dir if snapshot_dir.is_absolute() else ROOT / snapshot_dir
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    print(f"Capturing {url} ...", flush=True)
    o = AgentOrchestrator()
    result = o.delegate("analyze frontend", {"agent": "vision", "url": url, "full_page": True})

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    import base64
    if result.get("image_base64"):
        png_path = snapshot_dir / "screenshot.png"
        png_path.write_bytes(base64.b64decode(result["image_base64"]))
        print(f"Wrote {png_path}")
    lines = [
        f"URL: {result.get('url', '')}",
        f"Title: {result.get('title', '')}",
        f"Viewport: {result.get('viewport', {})}",
        "",
        "Interactive elements:",
    ]
    for el in result.get("interactive_elements") or []:
        lines.append(f"  - {el.get('tag', '')} {el.get('text', '')[:60]} (id={el.get('id')}, role={el.get('role')})")
    summary_path = snapshot_dir / "frontend-summary.txt"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {summary_path}")
    print("AI can read these files to see your frontend.")


if __name__ == "__main__":
    main()
