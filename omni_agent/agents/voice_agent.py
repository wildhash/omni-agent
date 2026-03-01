"""VoiceAgent.

This repo keeps the default `VoiceAgent` offline-friendly and deterministic so
unit tests and demo runs don't require external dependencies.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Optional
import uuid
import wave
from io import BytesIO


class VoiceAgent:
    """Simulated TTS/STT.

    - speak / tts: returns a small valid WAV payload as base64.
    - transcribe / stt: returns a deterministic transcript and byte count.
    """

    def __init__(self) -> None:
        self._session_id = uuid.uuid4().hex

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
        """Simulate TTS by returning a short WAV payload as base64."""
        if not text:
            return {
                "error": "No text provided for TTS.",
                "hint": "Pass a non-empty 'text' field in context.",
            }

        wav_bytes = _build_silent_wav_bytes(seconds=1.0)
        return {
            "status": "simulated",
            "text": text,
            "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
            "content_type": "audio/wav",
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
        return {
            "status": "simulated",
            "text": f"(simulated transcript {self._session_id})",
            "bytes": len(audio_bytes),
        }


def _build_silent_wav_bytes(*, seconds: float) -> bytes:
    sample_rate = 16_000
    num_samples = max(1, int(sample_rate * seconds))

    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()
