"""Gradio UI for Omni-Agent.

Install UI dependencies:

    pip install -r requirements-ui.txt

Run:

    python -m omni_agent.ui.gradio_app
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import tempfile
import atexit
import os
import wave
from collections import deque
from pathlib import Path
from typing import Any, Dict, Tuple

from omni_agent.orchestrator import AgentOrchestrator


class GradioNotInstalledError(RuntimeError):
    pass


def _load_gradio():
    try:
        import gradio as gr  # type: ignore

        return gr
    except ImportError as exc:
        raise GradioNotInstalledError(
            "Gradio UI is optional and not installed. Run: pip install -r requirements-ui.txt"
        ) from exc


def _parse_context(raw: str) -> Tuple[Dict[str, Any], str | None]:
    raw = (raw or "").strip()
    if not raw:
        return {}, None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "Context must be a valid JSON object."

    if not isinstance(value, dict):
        return {}, "Context must be a JSON object (e.g. {\"agent\": \"web\"})."

    return value, None


def build_app() -> Any:
    gr = _load_gradio()
    orchestrator = AgentOrchestrator()
    tts_files: deque[str] = deque()
    max_tts_files = 32

    @atexit.register
    def _cleanup_tts_files() -> None:
        for path in list(tts_files):
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    def run_task(task: str, context_json: str) -> Dict[str, Any]:
        ctx, err = _parse_context(context_json)
        if err:
            return {"error": err}
        return orchestrator.delegate(task, ctx)

    def tts(text: str):
        result = orchestrator.delegate(
            "speak",
            {"agent": "voice", "action": "speak", "text": text},
        )
        if "audio_base64" not in result:
            return None, result

        try:
            data = base64.b64decode(result["audio_base64"])
        except (ValueError, binascii.Error) as exc:
            return None, {
                "status": "error",
                "error": "VoiceAgent returned an invalid audio_base64 payload.",
                "hint": "Check the voice backend and try again.",
                "details": str(exc),
                "voice_result": result,
            }

        if not data:
            return None, {
                "status": "error",
                "error": "VoiceAgent returned an empty audio payload.",
                "hint": "Check the voice backend and try again.",
                "voice_result": result,
            }

        try:
            with wave.open(io.BytesIO(data), "rb") as wav:
                if wav.getnframes() == 0:
                    return None, {
                        "status": "error",
                        "error": "VoiceAgent returned a WAV payload with no audio frames.",
                        "hint": "Check the voice backend and try again.",
                        "voice_result": result,
                    }
        except wave.Error as exc:
            return None, {
                "status": "error",
                "error": "VoiceAgent returned an invalid WAV payload.",
                "hint": "Check the voice backend and try again.",
                "details": str(exc),
                "voice_result": result,
            }
        wav_path = None
        fd = None
        try:
            fd, path = tempfile.mkstemp(prefix="omni-agent-tts-", suffix=".wav")
            wav_path = path
            with os.fdopen(fd, "wb") as fh:
                fd = None
                fh.write(data)
        except OSError as exc:
            try:
                if fd is not None:
                    os.close(fd)
                if wav_path:
                    Path(wav_path).unlink(missing_ok=True)
            except OSError:
                pass
            return None, {
                "status": "error",
                "error": "Unable to write temporary WAV file for playback.",
                "hint": "Check filesystem permissions and available disk space.",
                "details": str(exc),
                "voice_result": result,
            }

        tts_files.append(wav_path)
        while len(tts_files) > max_tts_files:
            old_path = tts_files.popleft()
            try:
                Path(old_path).unlink(missing_ok=True)
            except OSError:
                pass

        return wav_path, result

    def stt(audio_path: Any):
        if not audio_path or not isinstance(audio_path, str):
            return "", {
                "error": (
                    "No audio filepath received from UI. "
                    "Ensure the Audio input uses type='filepath' and record or upload a single audio file."
                ),
                "received_type": str(type(audio_path)),
            }
        result = orchestrator.delegate(
            "transcribe",
            {"agent": "voice", "action": "transcribe", "audio_path": audio_path},
        )
        return result.get("text", ""), result

    with gr.Blocks(title="Omni-Agent") as demo:
        gr.Markdown(
            """
            # Omni-Agent

            Lightweight demo UI for delegating tasks to the orchestrator.
            """
        )

        with gr.Tab("Task"):
            task = gr.Textbox(
                label="Task",
                placeholder="e.g. book flight from SFO to NYC",
            )
            context_json = gr.Textbox(
                label="Context (JSON)",
                placeholder='e.g. {"date": "2026-03-15"}',
                lines=4,
            )
            run = gr.Button("Run")
            out = gr.JSON(label="Result")
            run.click(run_task, inputs=[task, context_json], outputs=[out])

        with gr.Tab("Voice"):
            gr.Markdown("## Text to speech (simulated)")
            tts_text = gr.Textbox(label="Text", placeholder="Say something")
            tts_run = gr.Button("Speak")
            tts_audio = gr.Audio(label="Audio", type="filepath")
            tts_raw = gr.JSON(label="Result")
            tts_run.click(tts, inputs=[tts_text], outputs=[tts_audio, tts_raw])

            gr.Markdown("## Speech to text (simulated)")
            stt_audio_in = gr.Audio(label="Input audio", type="filepath")
            stt_run = gr.Button("Transcribe")
            stt_text_out = gr.Textbox(label="Transcription")
            stt_raw = gr.JSON(label="Result")
            stt_run.click(stt, inputs=[stt_audio_in], outputs=[stt_text_out, stt_raw])

    return demo


def main() -> None:
    try:
        app = build_app()
    except GradioNotInstalledError as exc:
        raise SystemExit(str(exc)) from exc

    app.launch()


if __name__ == "__main__":
    main()
