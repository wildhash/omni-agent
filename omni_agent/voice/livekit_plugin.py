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
import binascii
import io
import json
import logging
import os
import signal
import wave
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

from omni_agent.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

AUDIO_SAMPLE_RATE = 16_000
AUDIO_NUM_CHANNELS = 1
AUDIO_SAMPLE_WIDTH = 2


class LiveKitNotInstalledError(RuntimeError):
    pass


def _load_livekit():
    try:
        from livekit import api as lk_api  # type: ignore
        from livekit import rtc as lk_rtc  # type: ignore

        if not hasattr(lk_api, "AccessToken") or not hasattr(lk_rtc, "Room"):
            raise LiveKitNotInstalledError(
                "LiveKit SDK appears incompatible. Try upgrading 'livekit' or reinstalling via requirements-livekit.txt"
            )

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

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"ws", "wss"}:
        raise ValueError("LIVEKIT_URL must start with ws:// or wss://")
    if not parsed_url.netloc:
        raise ValueError(f"LIVEKIT_URL must include a hostname, got: {url!r}")

    room = os.getenv("LIVEKIT_ROOM", "omni-agent").strip() or "omni-agent"
    identity = os.getenv("LIVEKIT_IDENTITY", "omni-agent").strip() or "omni-agent"
    name = os.getenv("LIVEKIT_NAME", identity).strip() or identity
    raw_publish_audio = os.getenv("LIVEKIT_PUBLISH_AUDIO", "1").strip().lower()
    if raw_publish_audio in {"0", "false", "no", "off"}:
        publish_audio = False
    elif raw_publish_audio in {"1", "true", "yes", "on"}:
        publish_audio = True
    else:
        raise ValueError(
            f"LIVEKIT_PUBLISH_AUDIO={raw_publish_audio!r} must be one of: 0, 1, true, false, yes, no, on, off"
        )

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


def _inspect_wav(wav_bytes: bytes) -> Optional[Dict[str, int]]:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            return {
                "sample_rate": wav.getframerate(),
                "num_channels": wav.getnchannels(),
                "sample_width": wav.getsampwidth(),
                "num_frames": wav.getnframes(),
            }
    except wave.Error as exc:
        logger.warning("LiveKit plugin failed to parse WAV payload: %s", exc)
        return None


async def _play_wav_bytes(audio_source: Any, lk_rtc: Any, wav_bytes: bytes) -> None:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        sample_rate = wav.getframerate()
        num_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()

        if sample_width != AUDIO_SAMPLE_WIDTH:
            logger.warning(
                "LiveKit plugin skipping WAV playback due to unsupported sample width %s (expected %s)",
                sample_width,
                AUDIO_SAMPLE_WIDTH,
            )
            return
        if sample_rate != AUDIO_SAMPLE_RATE or num_channels != AUDIO_NUM_CHANNELS:
            logger.warning(
                "LiveKit plugin skipping WAV playback due to unsupported format (sr=%s ch=%s; expected sr=%s ch=%s)",
                sample_rate,
                num_channels,
                AUDIO_SAMPLE_RATE,
                AUDIO_NUM_CHANNELS,
            )
            return

        chunk_samples = int(sample_rate * 0.02)  # 20ms
        while True:
            pcm = wav.readframes(chunk_samples)
            if not pcm:
                break

            frame_bytes = AUDIO_SAMPLE_WIDTH * num_channels
            if len(pcm) % frame_bytes != 0:
                logger.warning("LiveKit plugin encountered malformed PCM frame; stopping playback")
                break

            samples_per_channel = len(pcm) // (2 * num_channels)
            frame = lk_rtc.AudioFrame(
                pcm,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel,
            )
            audio_source.capture_frame(frame)
            sleep_seconds: Any = frame.duration
            if hasattr(sleep_seconds, "total_seconds"):
                sleep_seconds = sleep_seconds.total_seconds()
            await asyncio.sleep(float(sleep_seconds))


async def run_livekit_plugin(config: LiveKitConfig) -> None:
    _, lk_rtc = _load_livekit()

    orchestrator = AgentOrchestrator()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    task_queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=64)
    tts_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=16)

    room = lk_rtc.Room()
    audio_source = None
    audio_track = None
    if config.publish_audio:
        audio_source = lk_rtc.AudioSource(sample_rate=AUDIO_SAMPLE_RATE, num_channels=AUDIO_NUM_CHANNELS)
        audio_track = lk_rtc.LocalAudioTrack.create_audio_track("omni-agent-tts", audio_source)

    async def _tts_worker() -> None:
        if audio_source is None:
            return
        while True:
            if stop_event.is_set() and tts_queue.empty():
                break
            try:
                wav_bytes = await asyncio.wait_for(tts_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                await _play_wav_bytes(audio_source, lk_rtc, wav_bytes)
            finally:
                tts_queue.task_done()

    async def _task_worker() -> None:
        while True:
            if stop_event.is_set() and task_queue.empty():
                break
            try:
                packet, message = await asyncio.wait_for(task_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                await _handle_task(packet, message)
            finally:
                task_queue.task_done()

    async def _handle_task(packet: Any, message: Dict[str, Any]) -> None:
        task = str(message.get("task", "")).strip()
        if not task:
            return

        context = message.get("context")
        if not isinstance(context, dict):
            context = {}

        task_lower = task.lower()
        agent_hint = str(context.get("agent", "")).strip().lower()
        if agent_hint != "voice":
            result = {
                "error": "LiveKit voice plugin only supports voice tasks.",
                "hint": "Set context.agent='voice' and use action 'speak' or 'transcribe'.",
            }
        elif task_lower not in {"speak", "transcribe", "tts", "stt"}:
            result = {
                "error": "LiveKit voice plugin only supports tasks: speak, transcribe.",
                "hint": "Send task='speak' or task='transcribe' with the appropriate context.action.",
            }
        else:
            result = orchestrator.delegate(task, context)

        audio_b64 = result.get("audio_base64")
        if audio_b64 and audio_source is not None:
            base64_error = None
            try:
                wav_bytes = base64.b64decode(audio_b64)
            except (ValueError, binascii.Error) as exc:
                wav_bytes = b""
                base64_error = str(exc)

            if wav_bytes:
                wav_info = _inspect_wav(wav_bytes)
                expected = {
                    "sample_rate": AUDIO_SAMPLE_RATE,
                    "num_channels": AUDIO_NUM_CHANNELS,
                    "sample_width": AUDIO_SAMPLE_WIDTH,
                }
                if wav_info is None:
                    logger.warning("LiveKit plugin received invalid WAV; skipping audio playback")
                    result = {
                        **result,
                        "livekit_audio_error": "invalid_wav",
                        "livekit_warning": "Invalid WAV payload; unable to play audio.",
                    }
                elif wav_info.get("num_frames", 0) == 0:
                    logger.warning("LiveKit plugin received WAV payload with no audio frames")
                    result = {
                        **result,
                        "livekit_audio_error": "empty_wav",
                        "livekit_warning": "WAV payload contains no audio frames.",
                    }
                elif (
                    wav_info.get("sample_width") != AUDIO_SAMPLE_WIDTH
                    or wav_info.get("sample_rate") != AUDIO_SAMPLE_RATE
                    or wav_info.get("num_channels") != AUDIO_NUM_CHANNELS
                ):
                    logger.warning(
                        "LiveKit plugin received unsupported WAV format %s (expected %s); skipping playback",
                        wav_info,
                        expected,
                    )
                    result = {
                        **result,
                        "livekit_audio_error": "unsupported_wav_format",
                        "livekit_warning": "Unsupported WAV format; unable to play audio.",
                        "livekit_wav": wav_info,
                        "livekit_expected_wav": expected,
                    }
                else:
                    if stop_event.is_set():
                        result = {
                            **result,
                            "livekit_audio_error": "shutdown_in_progress",
                            "livekit_warning": "Shutdown in progress; skipping audio playback.",
                        }
                    else:
                        try:
                            tts_queue.put_nowait(wav_bytes)
                        except asyncio.QueueFull:
                            logger.warning("LiveKit plugin TTS queue full; dropping audio playback")
                            result = {
                                **result,
                                "livekit_audio_error": "tts_queue_full",
                                "livekit_warning": "TTS queue is full; dropping audio playback.",
                            }
            elif base64_error:
                logger.warning("LiveKit plugin received invalid audio_base64: %s", base64_error)
                result = {
                    **result,
                    "livekit_audio_error": "invalid_base64",
                    "livekit_audio_error_details": base64_error,
                    "livekit_warning": "Invalid base64 encoding for audio; unable to play TTS.",
                }

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

    def _on_data_received(packet: Any) -> None:
        if packet.topic != config.task_topic:
            return
        try:
            message = json.loads(packet.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning(
                "LiveKit plugin received invalid JSON on topic %s: %s (len=%d)",
                packet.topic,
                exc,
                len(packet.data),
            )

            def _send_error() -> None:
                destination_identities = []
                if getattr(packet, "participant", None) is not None:
                    destination_identities = [packet.participant.identity]
                payload = json.dumps(
                    {
                        "task": "",
                        "result": {
                            "error": "Invalid JSON payload.",
                            "hint": "Send a JSON object like {\"task\": \"speak\", \"context\": {...}}.",
                            "details": str(exc),
                        },
                    },
                    ensure_ascii=False,
                )
                try:
                    room.local_participant.publish_data(
                        payload,
                        reliable=True,
                        destination_identities=destination_identities,
                        topic=config.result_topic,
                    )
                except Exception:
                    logger.exception("LiveKit plugin unable to publish JSON parse error response")

            loop.call_soon_threadsafe(_send_error)
            return
        if not isinstance(message, dict):
            logger.warning(
                "LiveKit plugin received non-object message on topic %s: %s",
                packet.topic,
                type(message).__name__,
            )

            def _send_error() -> None:
                destination_identities = []
                if getattr(packet, "participant", None) is not None:
                    destination_identities = [packet.participant.identity]
                payload = json.dumps(
                    {
                        "task": "",
                        "result": {
                            "error": "Message must be a JSON object.",
                            "hint": "Send a JSON object like {\"task\": \"speak\", \"context\": {...}}.",
                        },
                    },
                    ensure_ascii=False,
                )
                try:
                    room.local_participant.publish_data(
                        payload,
                        reliable=True,
                        destination_identities=destination_identities,
                        topic=config.result_topic,
                    )
                except Exception:
                    logger.exception("LiveKit plugin unable to publish message type error response")

            loop.call_soon_threadsafe(_send_error)
            return

        def _enqueue() -> None:
            try:
                task_queue.put_nowait((packet, message))
            except asyncio.QueueFull:
                logger.warning("LiveKit plugin task queue full; dropping packet")
                task = str(message.get("task", "")).strip()
                payload = json.dumps(
                    {
                        "task": task,
                        "result": {
                            "error": "LiveKit plugin overloaded; dropping task.",
                            "hint": "Reduce request rate or increase worker capacity.",
                        },
                    },
                    ensure_ascii=False,
                )
                destination_identities = []
                if getattr(packet, "participant", None) is not None:
                    destination_identities = [packet.participant.identity]
                try:
                    room.local_participant.publish_data(
                        payload,
                        reliable=True,
                        destination_identities=destination_identities,
                        topic=config.result_topic,
                    )
                except Exception:
                    logger.exception("LiveKit plugin unable to publish overload error response")

        loop.call_soon_threadsafe(_enqueue)

    room.on("data_received", _on_data_received)

    def _on_disconnected(*_args: Any, **_kwargs: Any) -> None:
        loop.call_soon_threadsafe(stop_event.set)

    room.on("disconnected", _on_disconnected)

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # pragma: no cover
            pass

    await room.connect(config.url, config.token)

    task_workers = [asyncio.create_task(_task_worker()) for _ in range(2)]

    if audio_track is not None:
        await room.local_participant.publish_track(audio_track)
        tts_worker = asyncio.create_task(_tts_worker())
    else:
        tts_worker = None

    await stop_event.wait()
    await room.disconnect()

    try:
        await asyncio.wait_for(task_queue.join(), timeout=2.0)
    except asyncio.TimeoutError:
        pass

    try:
        await asyncio.wait_for(tts_queue.join(), timeout=2.0)
    except asyncio.TimeoutError:
        pass

    for task in task_workers:
        task.cancel()
    if tts_worker is not None:
        tts_worker.cancel()

    await asyncio.gather(*task_workers, return_exceptions=True)
    if tts_worker is not None:
        await asyncio.gather(tts_worker, return_exceptions=True)

    if audio_source is not None:
        try:
            await audio_source.aclose()
        except Exception:
            logger.exception("LiveKit plugin failed to close audio_source cleanly")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )
    try:
        config = load_config_from_env()
        asyncio.run(run_livekit_plugin(config))
    except KeyboardInterrupt:
        return
    except LiveKitNotInstalledError as exc:
        raise SystemExit(str(exc)) from exc
    except ValueError as exc:
        raise SystemExit(f"Invalid LiveKit configuration: {exc}") from exc


if __name__ == "__main__":
    main()
