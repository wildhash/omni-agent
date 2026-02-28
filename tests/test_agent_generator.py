"""Tests for AgentGenerator."""

import os
from unittest.mock import MagicMock, patch

from omni_agent.agent_generator import AgentGenerator


def test_generate_agent_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generator = AgentGenerator()

    agent_code = (
        "class VoiceAgent:\n"
        "    def execute(self, task: str, context: dict) -> dict:\n"
        "        return {'status': 'ok'}\n"
    )
    with patch.object(generator.mistral, "generate_code", return_value=agent_code):
        result = generator.generate_agent("Voice")

    assert result["status"] == "success"
    assert result["agent_type"] == "Voice"
    assert os.path.exists(result["file"])


def test_generate_agent_error(monkeypatch):
    generator = AgentGenerator()

    with patch.object(
        generator.mistral, "generate_code", side_effect=Exception("API error")
    ):
        result = generator.generate_agent("Broken")

    assert result["status"] == "error"
    assert "API error" in result["message"]


def test_register_agent_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generator = AgentGenerator()

    agent_code = (
        "class SampleAgent:\n"
        "    def execute(self, task: str, context: dict) -> dict:\n"
        "        return {'status': 'ok'}\n"
    )
    mock_orchestrator = MagicMock()

    mock_agent_class = MagicMock()
    mock_module = MagicMock()
    mock_module.SampleAgent = mock_agent_class

    with patch.object(generator.mistral, "generate_code", return_value=agent_code):
        with patch("importlib.import_module", return_value=mock_module):
            result = generator.register_agent(mock_orchestrator, "Sample")

    assert result["status"] == "success"
    mock_orchestrator.add_agent.assert_called_once()


def test_register_agent_propagates_error(monkeypatch):
    generator = AgentGenerator()

    with patch.object(
        generator.mistral, "generate_code", side_effect=Exception("fail")
    ):
        result = generator.register_agent(MagicMock(), "Fail")

    assert result["status"] == "error"
