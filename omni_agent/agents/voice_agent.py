"""VoiceAgent: real TTS (gTTS) and STT (Whisper)."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, Dict, Optional


class VoiceAgent:
    """Real text-to-speech (gTTS) and speech-to-text (Whisper).

    - speak / tts: gTTS → WAV (via pydub), returned as base64.
    - transcribe / stt: Whisper transcription from audio file or base64.
    """

    def __init__(self) -> None:
        self._whisper_model = None

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        action = str(context.get("action", "")).strip().lower()
        task_lower = task.lower()

        if action in {"speak", "tts"} or any(
            kw in task_lower for kw in ("speak", "tts", "text to speech")
        ):
            return self._speak(context.get("text", ""))

        if action in {"transcribe", "stt"} or any(
            kw in task_lower for kw in ("transcribe", "stt", "speech to text")
        ):
            return self._transcribe(
                audio_base64=context.get("audio_base64"),
                audio_path=context.get("audio_path"),
            )

        return {
            "error": f"Voice task not recognized: '{task}'",
            "hint": "Use an 'action' of 'speak' or 'transcribe' in context.",
        }

    def _speak(self, text: str) -> Dict[str, Any]:
        """Real TTS via gTTS. Returns MP3 as base64 (no ffmpeg required)."""
        if not text:
            return {
                "error": "No text provided for TTS.",
                "hint": "Pass a non-empty 'text' field in context.",
            }
        try:
            from gtts import gTTS
        except ImportError as e:
            return {
                "error": f"TTS dependencies missing: {e}",
                "hint": "Run: pip install gtts",
            }
        try:
            mp3_fp = io.BytesIO()
            tts = gTTS(text=text, lang="en", slow=False)
            tts.write_to_fp(mp3_fp)
            mp3_bytes = mp3_fp.getvalue()
        except Exception as exc:
            return {
                "error": str(exc),
                "hint": "Check network (gTTS uses Google).",
            }
        return {
            "status": "success",
            "text": text,
            "audio_base64": base64.b64encode(mp3_bytes).decode("ascii"),
            "content_type": "audio/mpeg",
        }

    def _transcribe(
        self,
        *,
        audio_base64: str | None,
        audio_path: str | None,
    ) -> Dict[str, Any]:
        """Real STT via Whisper."""
        audio_bytes = b""
        if audio_base64 and audio_path:
            return {
                "error": "Provide only one of audio_base64 or audio_path, not both.",
                "hint": "Provide exactly one audio input in context.",
            }
        if audio_base64:
            try:
                audio_bytes = base64.b64decode(audio_base64, validate=True)
            except ValueError:
                return {
                    "error": "Invalid audio_base64 payload.",
                    "hint": "Provide base64-encoded audio bytes.",
                }
        elif audio_path:
            try:
                audio_bytes = Path(audio_path).read_bytes()
            except OSError:
                return {
                    "error": f"Unable to read audio_path: {audio_path}",
                    "hint": "Provide a readable file path in 'audio_path'.",
                }
        else:
            return {
                "error": "No audio provided for transcription.",
                "hint": "Provide exactly one of 'audio_base64' or 'audio_path' in context.",
            }
        try:
            import whisper
        except ImportError:
            return {
                "error": "Whisper is not installed.",
                "hint": "Run: pip install openai-whisper",
            }

        try:
            if self._whisper_model is None:
                self._whisper_model = whisper.load_model("base")
            model = self._whisper_model
        except Exception as exc:
            return {
                "error": f"Failed to load Whisper model: {exc}",
                "hint": "Run: pip install openai-whisper. First run downloads the model.",
            }

        path_to_use: str | None = None
        if audio_path and Path(audio_path).exists():
            path_to_use = audio_path
        if path_to_use is None:
            if not audio_bytes:
                return {"error": "Audio is empty.", "hint": "Provide non-empty audio."}
            import tempfile
            suffix = ".wav"
            if audio_bytes[:3] == b"ID3" or (len(audio_bytes) >= 2 and audio_bytes[:2] == b"\xff\xfb"):
                suffix = ".mp3"
            elif audio_bytes[:4] != b"RIFF":
                suffix = ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio_bytes)
                path_to_use = f.name

        try:
            result = model.transcribe(path_to_use, fp16=False, language="en")
            text = (result.get("text") or "").strip()
        except Exception as exc:
            return {
                "error": str(exc),
                "hint": "Ensure audio is WAV/MP3 or a format Whisper supports. Try recording again.",
            }
        finally:
            if path_to_use and path_to_use != audio_path:
                Path(path_to_use).unlink(missing_ok=True)

        return {
            "status": "success",
            "text": text or "(no speech detected)",
            "bytes": len(audio_bytes),
        }
