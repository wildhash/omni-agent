"""VoiceAgent: basic voice I/O primitives for demos.

This project intentionally keeps voice features lightweight and offline-friendly.
For now, the agent simulates speech-to-text and text-to-speech so the rest of
the system can exercise a "voice" workflow without requiring external services.
"""

from __future__ import annotations

import binascii
import base64
import io
import math
import wave
from pathlib import Path
from typing import Any, Dict, Optional


class VoiceAgent:
    """Handle simple voice I/O operations.

    Supported tasks
    ---------------
    - speak: generate a short WAV tone payload for a given text.
    - transcribe: return a simulated transcription for provided audio.

    Notes
    -----
    The current implementation is intentionally "simulated". It produces a tiny
    WAV blob so UIs (like Gradio) can render an audio output without adding
    heavy dependencies.
    """

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
                audio_b64=context.get("audio_base64"),
                audio_path=context.get("audio_path"),
            )

        return {"error": f"Voice task not recognised: '{task}'"}

    def _speak(self, text: str) -> Dict[str, Any]:
        """Return a tiny WAV tone payload as base64.

        Parameters
        ----------
        text:
            Text to "speak".
        """
        if not text:
            return {"error": "No text provided."}

        wav_bytes = self._tone_wav_bytes(duration_s=0.25)
        return {
            "status": "simulated",
            "text": text,
            "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
            "content_type": "audio/wav",
        }

    def _transcribe(
        self,
        *,
        audio_b64: str | None,
        audio_path: str | None,
    ) -> Dict[str, Any]:
        """Return a simulated transcription.

        Parameters
        ----------
        audio_b64:
            Base64-encoded audio bytes.
        audio_path:
            Path to an audio file on disk.
        """
        audio_bytes = b""

        if audio_b64 and audio_path:
            return {"error": "Provide only one of audio_base64 or audio_path, not both."}

        if audio_b64:
            try:
                audio_bytes = base64.b64decode(audio_b64, validate=True)
            except (binascii.Error, ValueError) as exc:
                return {"error": f"Invalid audio_base64: {exc}"}
        elif audio_path:
            try:
                audio_bytes = Path(audio_path).read_bytes()
            except OSError:
                return {"error": f"Unable to read audio_path: {audio_path}"}
        else:
            return {"error": "No audio provided."}

        return {
            "status": "simulated",
            "bytes": len(audio_bytes),
            "text": "[simulated transcription]",
        }

    def _tone_wav_bytes(self, *, duration_s: float) -> bytes:
        sample_rate = 16_000
        frequency_hz = 440.0
        amplitude = 0.2
        frames = int(sample_rate * duration_s)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit PCM
            wav.setframerate(sample_rate)

            samples = bytearray()
            for i in range(frames):
                t = i / sample_rate
                value = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * frequency_hz * t))
                samples += value.to_bytes(2, byteorder="little", signed=True)

            wav.writeframes(samples)

        return buf.getvalue()
