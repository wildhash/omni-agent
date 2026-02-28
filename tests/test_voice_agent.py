"""Tests for VoiceAgent."""

import base64

from omni_agent.agents.voice_agent import VoiceAgent


def test_speak_returns_audio_base64():
    agent = VoiceAgent()
    result = agent.execute("speak", {"text": "hello"})
    assert result["status"] == "simulated"
    assert result["text"] == "hello"

    audio = base64.b64decode(result["audio_base64"])
    assert audio[:4] == b"RIFF"  # WAV header


def test_transcribe_requires_audio():
    agent = VoiceAgent()
    result = agent.execute("transcribe", {})
    assert "error" in result


def test_transcribe_accepts_audio_base64():
    agent = VoiceAgent()
    payload = base64.b64encode(b"fake-audio").decode("ascii")
    result = agent.execute("transcribe", {"audio_base64": payload})
    assert result["status"] == "simulated"
    assert result["bytes"] == len(b"fake-audio")
    assert "text" in result


def test_unknown_task_returns_error():
    agent = VoiceAgent()
    result = agent.execute("dance")
    assert "error" in result
