"""LiveKit voice plugin for Omni-Agent.

This module is intentionally lightweight: it doesn't try to be a full voice
assistant. Instead, it bridges a LiveKit room to the existing
:class:`~omni_agent.orchestrator.AgentOrchestrator`.

Protocol
--------

Send JSON data messages to the topic ``omni-agent/task``:

.. code-block:: json

    {"task": "speak", "context": {"agent": "voice", "action": "speak", "text": "hello"}}

The plugin replies on the topic ``omni-agent/result``:

.. code-block:: json

    {"task": "...", "result": {"status": "simulated", ...}}

If the delegated result contains ``audio_base64`` (WAV), the plugin will also
play it out via a published LiveKit audio track named ``omni-agent-tts``.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import signal
import wave
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from omni_agent.orchestrator import AgentOrchestrator


class LiveKitNotInstalledError(RuntimeError):
    pass


def _load_livekit():
    try:
        from livekit import api as lk_api  # type: ignore
        from livekit import rtc as lk_rtc  # type: ignore

        return lk_api, lk_rtc
    except ImportError as exc:  # pragma: no cover
        raise LiveKitNotInstalledError(
            "LiveKit plugin is optional and not installed. Run: pip install -r requirements-livekit.txt"
        ) from exc


@dataclass(frozen=True)
class LiveKitConfig:
    url: str
    token: str
    room: str
    identity: str
    name: str
    task_topic: str = "omni-agent/task"
    result_topic: str = "omni-agent/result"
    publish_audio: bool = True


def _build_token(*, api_key: str, api_secret: str, room: str, identity: str, name: str) -> str:
    lk_api, _ = _load_livekit()
    grants = lk_api.VideoGrants(room_join=True, room=room)
    token = (
        lk_api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_ttl(timedelta(hours=1))
        .to_jwt()
    )
    return token


def load_config_from_env() -> LiveKitConfig:
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url:
        raise ValueError("LIVEKIT_URL is required")

    room = os.getenv("LIVEKIT_ROOM", "omni-agent").strip() or "omni-agent"
    identity = os.getenv("LIVEKIT_IDENTITY", "omni-agent").strip() or "omni-agent"
    name = os.getenv("LIVEKIT_NAME", identity).strip() or identity
    publish_audio = os.getenv("LIVEKIT_PUBLISH_AUDIO", "1").strip() == "1"

    token = os.getenv("LIVEKIT_TOKEN", "").strip()
    if not token:
        api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
        api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
        if not api_key or not api_secret:
            raise ValueError(
                "LIVEKIT_TOKEN is required, or both LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set"
            )
        token = _build_token(
            api_key=api_key,
            api_secret=api_secret,
            room=room,
            identity=identity,
            name=name,
        )

    return LiveKitConfig(
        url=url,
        token=token,
        room=room,
        identity=identity,
        name=name,
        publish_audio=publish_audio,
    )


async def _play_wav_bytes(audio_source: Any, lk_rtc: Any, wav_bytes: bytes) -> None:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        sample_rate = wav.getframerate()
        num_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()

        if sample_width != 2:
            return
        if sample_rate != audio_source.sample_rate or num_channels != audio_source.num_channels:
            return

        chunk_samples = int(sample_rate * 0.02)  # 20ms
        while True:
            pcm = wav.readframes(chunk_samples)
            if not pcm:
                break

            samples_per_channel = len(pcm) // (2 * num_channels)
            frame = lk_rtc.AudioFrame(
                pcm,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel,
            )
            audio_source.capture_frame(frame)
            await asyncio.sleep(frame.duration)


async def run_livekit_plugin(config: LiveKitConfig) -> None:
    _, lk_rtc = _load_livekit()

    orchestrator = AgentOrchestrator()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    tts_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=16)

    room = lk_rtc.Room()
    audio_source = None
    audio_track = None
    if config.publish_audio:
        audio_source = lk_rtc.AudioSource(sample_rate=16_000, num_channels=1)
        audio_track = lk_rtc.LocalAudioTrack.create_audio_track("omni-agent-tts", audio_source)

    async def _tts_worker() -> None:
        if audio_source is None:
            return
        while True:
            wav_bytes = await tts_queue.get()
            try:
                await _play_wav_bytes(audio_source, lk_rtc, wav_bytes)
            finally:
                tts_queue.task_done()

    async def _handle_task(packet: Any) -> None:
        if packet.topic != config.task_topic:
            return

        try:
            message = json.loads(packet.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        task = str(message.get("task", "")).strip()
        if not task:
            return

        context = message.get("context")
        if not isinstance(context, dict):
            context = {}

        result = orchestrator.delegate(task, context)
        response = json.dumps({"task": task, "result": result}, ensure_ascii=False)

        destination_identities = []
        if getattr(packet, "participant", None) is not None:
            destination_identities = [packet.participant.identity]

        room.local_participant.publish_data(
            response,
            reliable=True,
            destination_identities=destination_identities,
            topic=config.result_topic,
        )

        audio_b64 = result.get("audio_base64")
        if audio_b64 and audio_source is not None:
            try:
                wav_bytes = base64.b64decode(audio_b64, validate=True)
            except ValueError:
                return
            try:
                tts_queue.put_nowait(wav_bytes)
            except asyncio.QueueFull:
                pass

    def _on_data_received(packet: Any) -> None:
        loop.call_soon_threadsafe(lambda: asyncio.create_task(_handle_task(packet)))

    room.on("data_received", _on_data_received)

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # pragma: no cover
            pass

    await room.connect(config.url, config.token)

    if audio_track is not None:
        await room.local_participant.publish_track(audio_track)
        asyncio.create_task(_tts_worker())

    await stop_event.wait()
    await room.disconnect()
    if audio_source is not None:
        await audio_source.aclose()


def main() -> None:
    try:
        config = load_config_from_env()
    except LiveKitNotInstalledError as exc:
        raise SystemExit(str(exc)) from exc
    except ValueError as exc:
        raise SystemExit(f"Invalid LiveKit configuration: {exc}") from exc

    try:
        asyncio.run(run_livekit_plugin(config))
    except LiveKitNotInstalledError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
