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

from dotenv import load_dotenv

load_dotenv()

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
    _orchestrator: Any = None

    def get_orchestrator():
        nonlocal _orchestrator
        if _orchestrator is None:
            from omni_agent.orchestrator import AgentOrchestrator
            _orchestrator = AgentOrchestrator()
        return _orchestrator

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
        return get_orchestrator().delegate(task, ctx)

    def tts(text: str):
        result = get_orchestrator().delegate(
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

        content_type = (result.get("content_type") or "audio/wav").lower()
        is_mp3 = "mpeg" in content_type or "mp3" in content_type
        suffix = ".mp3" if is_mp3 else ".wav"

        if not is_mp3:
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

        out_path = None
        fd = None
        try:
            fd, path = tempfile.mkstemp(prefix="omni-agent-tts-", suffix=suffix)
            out_path = path
            with os.fdopen(fd, "wb") as fh:
                fd = None
                fh.write(data)
        except OSError as exc:
            try:
                if fd is not None:
                    os.close(fd)
                if out_path:
                    Path(out_path).unlink(missing_ok=True)
            except OSError:
                pass
            return None, {
                "status": "error",
                "error": "Unable to write temporary audio file for playback.",
                "hint": "Check filesystem permissions and available disk space.",
                "details": str(exc),
                "voice_result": result,
            }

        tts_files.append(out_path)
        while len(tts_files) > max_tts_files:
            old_path = tts_files.popleft()
            try:
                Path(old_path).unlink(missing_ok=True)
            except OSError:
                pass

        return out_path, result

    def stt(audio_path: Any):
        if not audio_path or not isinstance(audio_path, str):
            return "", {
                "error": (
                    "No audio filepath received from UI. "
                    "Ensure the Audio input uses type='filepath' and record or upload a single audio file."
                ),
                "received_type": str(type(audio_path)),
            }
        result = get_orchestrator().delegate(
            "transcribe",
            {"agent": "voice", "action": "transcribe", "audio_path": audio_path},
        )
        return result.get("text", ""), result

    with gr.Blocks(title="Omni-Agent") as demo:
        gr.Markdown(
            """
            # Omni-Agent

            Multi-agent orchestration: **Task** (web, code, voice), **Voice** (TTS/STT), **Vision** (screenshot, DOM analysis, visual diff).
            """
        )

        with gr.Tab("Task"):
            task = gr.Textbox(
                label="Task",
                placeholder="e.g. book flight from SFO to NYC, browse web, run code, speak, screenshot",
            )
            context_json = gr.Textbox(
                label="Context (JSON)",
                placeholder='e.g. {"url": "https://example.com"} or {"from": "SFO", "to": "NYC", "date": "2026-03-15"}',
                lines=4,
            )
            run = gr.Button("Run")
            out = gr.JSON(label="Result")
            run.click(run_task, inputs=[task, context_json], outputs=[out])

        with gr.Tab("Voice"):
            gr.Markdown("## Text to speech (gTTS)")
            tts_text = gr.Textbox(label="Text", placeholder="Enter text to speak")
            tts_run = gr.Button("Speak")
            tts_audio = gr.Audio(label="Audio", type="filepath")
            tts_raw = gr.JSON(label="Result")
            tts_run.click(tts, inputs=[tts_text], outputs=[tts_audio, tts_raw])

            gr.Markdown("## Speech to text (Whisper)")
            stt_audio_in = gr.Audio(label="Input audio", type="filepath")
            stt_run = gr.Button("Transcribe")
            stt_text_out = gr.Textbox(label="Transcription")
            stt_raw = gr.JSON(label="Result")
            stt_run.click(stt, inputs=[stt_audio_in], outputs=[stt_text_out, stt_raw])

        with gr.Tab("Vision"):
            gr.Markdown(
                "## Visual Dev Loop\n"
                "Point the VisionAgent at any running frontend to capture, "
                "inspect, and iterate on UI changes in real time."
            )

            with gr.Row():
                vision_url = gr.Textbox(
                    label="Target URL",
                    value="http://127.0.0.1:7860",
                    placeholder="http://localhost:3000",
                    scale=3,
                )
                vision_full = gr.Checkbox(label="Full page", value=True)

            with gr.Row():
                btn_capture = gr.Button("Screenshot", variant="primary")
                btn_analyze = gr.Button("Analyze DOM")
                btn_elements = gr.Button("List Elements")

            vision_img = gr.Image(label="Screenshot", type="filepath")
            vision_info = gr.JSON(label="Analysis", open=False)

            screenshot_files: deque[str] = deque()
            max_screenshot_files = 16

            def _capture(url: str, full_page: bool):
                result = get_orchestrator().delegate(
                    "screenshot",
                    {"agent": "vision", "url": url, "full_page": full_page},
                )
                if result.get("error"):
                    return None, result
                img_path = _save_vision_image(result, screenshot_files, max_screenshot_files)
                info = {k: v for k, v in result.items() if k != "image_base64"}
                return img_path, info

            def _analyze_ui(url: str, full_page: bool):
                result = get_orchestrator().delegate(
                    "analyze frontend",
                    {"agent": "vision", "url": url, "full_page": full_page},
                )
                if result.get("error"):
                    return None, result
                img_path = _save_vision_image(result, screenshot_files, max_screenshot_files)
                info = {k: v for k, v in result.items() if k != "image_base64"}
                return img_path, info

            def _get_elements(url: str, full_page: bool):
                result = get_orchestrator().delegate(
                    "list elements",
                    {"agent": "vision", "url": url, "full_page": full_page},
                )
                return None, result

            btn_capture.click(
                _capture, inputs=[vision_url, vision_full],
                outputs=[vision_img, vision_info],
            )
            btn_analyze.click(
                _analyze_ui, inputs=[vision_url, vision_full],
                outputs=[vision_img, vision_info],
            )
            btn_elements.click(
                _get_elements, inputs=[vision_url, vision_full],
                outputs=[vision_img, vision_info],
            )

            gr.Markdown("### Visual Diff")
            with gr.Row():
                diff_delay = gr.Slider(
                    minimum=1, maximum=15, value=3, step=1,
                    label="Delay between captures (seconds)",
                )
                btn_diff = gr.Button("Capture Diff")
            with gr.Row():
                diff_before = gr.Image(label="Before", type="filepath")
                diff_after = gr.Image(label="After", type="filepath")
            diff_info = gr.JSON(label="Diff Result", open=False)

            def _run_diff(url: str, delay_s: float):
                result = get_orchestrator().delegate(
                    "diff",
                    {"agent": "vision", "url": url, "delay_s": delay_s},
                )
                if result.get("error"):
                    return None, None, result
                before_path = None
                after_path = None
                if "before_base64" in result:
                    before_path = _save_b64_image(
                        result["before_base64"], screenshot_files, max_screenshot_files,
                    )
                if "after_base64" in result:
                    after_path = _save_b64_image(
                        result["after_base64"], screenshot_files, max_screenshot_files,
                    )
                info = {
                    k: v for k, v in result.items()
                    if k not in ("before_base64", "after_base64")
                }
                return before_path, after_path, info

            btn_diff.click(
                _run_diff, inputs=[vision_url, diff_delay],
                outputs=[diff_before, diff_after, diff_info],
            )

    return demo, gr


def _save_vision_image(
    result: Dict[str, Any],
    file_deque: deque,
    max_files: int,
) -> str | None:
    """Decode image_base64 from a vision result and write to a temp file."""
    b64 = result.get("image_base64")
    if not b64:
        return None
    return _save_b64_image(b64, file_deque, max_files)


def _save_b64_image(
    b64: str,
    file_deque: deque,
    max_files: int,
) -> str | None:
    """Write a base64-encoded PNG to a temp file and track it for cleanup."""
    try:
        data = base64.b64decode(b64)
    except Exception:
        return None
    try:
        fd, path = tempfile.mkstemp(prefix="omni-vision-", suffix=".png")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        file_deque.append(path)
        while len(file_deque) > max_files:
            old = file_deque.popleft()
            try:
                Path(old).unlink(missing_ok=True)
            except OSError:
                pass
        return path
    except OSError:
        return None


def main() -> None:
    try:
        app, gr = build_app()
    except GradioNotInstalledError as exc:
        raise SystemExit(str(exc)) from exc

    server_name = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    port_env = os.getenv("GRADIO_SERVER_PORT", "7860")
    server_port = int(port_env)
    share = os.getenv("GRADIO_SHARE", "").lower() in ("1", "true", "yes")
    # Gradio 6: theme at launch(); try next ports if default is in use
    ports_to_try = [server_port, server_port + 1, server_port + 2]
    last_err = None
    for port in ports_to_try:
        try:
            app.launch(
                server_name=server_name,
                server_port=port,
                share=share,
                theme=gr.themes.Soft(),
            )
            break
        except OSError as e:
            last_err = e
            if "empty port" in str(e).lower() or "10048" in str(e) or "address" in str(e).lower():
                if port != ports_to_try[-1]:
                    print(f"Port {port} in use, trying {port + 1} ...", flush=True)
                continue
            raise
    else:
        if last_err is not None:
            raise last_err


if __name__ == "__main__":
    main()
