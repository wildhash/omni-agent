#!/usr/bin/env python3
"""Run all orchestrator flows (Task, Voice, Vision) to verify the system works."""

import os
import sys

# Load env and add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from omni_agent.orchestrator import AgentOrchestrator


def main():
    o = AgentOrchestrator()
    failures = []

    # Task: browse web (real scrape)
    print("1. Task: browse web ...", end=" ", flush=True)
    r = o.delegate("browse web", {"url": "https://httpbin.org/html"})
    if r.get("status") == "success" and r.get("content"):
        print("OK (content len %d)" % len(r.get("content", "")))
    else:
        print("FAIL", r.get("error") or r)
        failures.append("browse web")

    # Task: book flight (real scrape)
    print("2. Task: book flight ...", end=" ", flush=True)
    r = o.delegate("book flight from SFO to NYC", {"from": "SFO", "to": "NYC", "date": "2026-03-15"})
    if r.get("status") == "success":
        print("OK")
    else:
        print("FAIL", r.get("error") or r)
        failures.append("book flight")

    # Voice: TTS
    print("3. Voice: TTS (gTTS) ...", end=" ", flush=True)
    r = o.delegate("speak", {"agent": "voice", "action": "speak", "text": "Hello"})
    if r.get("status") == "success" and r.get("audio_base64"):
        print("OK (%s)" % r.get("content_type", ""))
    else:
        print("FAIL", r.get("error") or r)
        failures.append("TTS")

    # Voice: STT (needs Whisper; optional)
    print("4. Voice: STT (Whisper) ...", end=" ", flush=True)
    try:
        import whisper
        whisper.load_model("base")
    except Exception:
        print("SKIP (pip install openai-whisper for STT)")
    else:
        # Minimal silent WAV for pipeline test
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 1600)
        buf.seek(0)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        try:
            r = o.delegate("transcribe", {"agent": "voice", "action": "transcribe", "audio_path": path})
            if r.get("status") == "success":
                print("OK")
            else:
                print("FAIL", r.get("error") or r)
                failures.append("STT")
        finally:
            os.path.exists(path) and os.unlink(path)

    # Vision: screenshot
    print("5. Vision: screenshot ...", end=" ", flush=True)
    r = o.delegate("screenshot", {"agent": "vision", "url": "https://example.com"})
    if r.get("status") == "success" and r.get("image_base64"):
        print("OK")
    else:
        print("FAIL", r.get("error") or r)
        failures.append("vision screenshot")

    if failures:
        print("\nFailed:", failures)
        sys.exit(1)
    print("\nAll flows OK.")


if __name__ == "__main__":
    main()
