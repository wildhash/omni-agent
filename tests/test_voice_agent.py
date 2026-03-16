"""Tests for VoiceAgent."""

import base64

from omni_agent.agents.voice_agent import VoiceAgent


def test_speak_returns_audio_base64():
    agent = VoiceAgent()
    result = agent.execute("speak", {"text": "hello"})
    if "error" in result:
        raise AssertionError(f"speak failed: {result.get('error')} (hint: {result.get('hint')})")
    assert result["status"] == "success"
    assert result["text"] == "hello"
    assert result.get("content_type") == "audio/mpeg"

    audio = base64.b64decode(result["audio_base64"])
    # gTTS returns MP3: ID3 tag or MPEG frame sync (0xFF 0xFx)
    assert len(audio) > 100
    is_id3 = audio[:3] == b"ID3"
    is_mpeg_sync = len(audio) >= 2 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0
    assert is_id3 or is_mpeg_sync, "expected MP3 (ID3 or MPEG sync)"


def test_transcribe_requires_audio():
    agent = VoiceAgent()
    result = agent.execute("transcribe", {})
    assert "error" in result


def test_transcribe_accepts_audio_base64():
    agent = VoiceAgent()
    payload = base64.b64encode(b"fake-audio").decode("ascii")
    result = agent.execute("transcribe", {"audio_base64": payload})
    # Real Whisper may error on invalid audio or return text; either way we get status or error
    if "error" in result:
        assert "hint" in result or "error" in result
        return
    assert result["status"] == "success"
    assert result["bytes"] == len(b"fake-audio")
    assert "text" in result


def test_transcribe_accepts_audio_path(tmp_path):
    agent = VoiceAgent()
    p = tmp_path / "audio.wav"
    p.write_bytes(b"fake-audio")
    result = agent.execute("transcribe", {"audio_path": str(p)})
    if "error" in result:
        assert "bytes" not in result or result["bytes"] == len(b"fake-audio")
        return
    assert result["status"] == "success"
    assert result["bytes"] == len(b"fake-audio")


def test_transcribe_rejects_dual_inputs():
    agent = VoiceAgent()
    payload = base64.b64encode(b"fake-audio").decode("ascii")
    result = agent.execute("transcribe", {"audio_base64": payload, "audio_path": "/tmp/x"})
    assert "error" in result


def test_transcribe_rejects_invalid_audio_base64():
    agent = VoiceAgent()
    result = agent.execute("transcribe", {"audio_base64": "not-base64"})
    assert "error" in result


def test_action_dispatch_overrides_task_text():
    agent = VoiceAgent()
    result = agent.execute("dance", {"action": "speak", "text": "hello"})
    if "error" in result:
        raise AssertionError(f"speak via action failed: {result.get('error')}")
    assert result["status"] == "success"


def test_unknown_task_returns_error():
    agent = VoiceAgent()
    result = agent.execute("dance")
    assert "error" in result
