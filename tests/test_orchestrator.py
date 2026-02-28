"""Tests for AgentOrchestrator."""

from unittest.mock import MagicMock

import pytest

from omni_agent.orchestrator import AgentOrchestrator


def test_delegate_to_web_agent():
    orchestrator = AgentOrchestrator()
    mock_web = MagicMock()
    mock_web.execute.return_value = {"status": "success"}
    orchestrator.agents["web"] = mock_web

    result = orchestrator.delegate("book flight from SFO to NYC")

    assert result == {"status": "success"}
    mock_web.execute.assert_called_once()


def test_delegate_to_code_agent():
    orchestrator = AgentOrchestrator()
    mock_code = MagicMock()
    mock_code.execute.return_value = {"stdout": "Hello\n", "returncode": 0}
    orchestrator.agents["code"] = mock_code

    result = orchestrator.delegate("execute python code", {"code": "print('Hello')"})

    assert result["returncode"] == 0
    mock_code.execute.assert_called_once()


def test_delegate_to_voice_agent():
    orchestrator = AgentOrchestrator()
    mock_voice = MagicMock()
    mock_voice.execute.return_value = {"status": "simulated"}
    orchestrator.agents["voice"] = mock_voice

    result = orchestrator.delegate("speak", {"text": "hello"})

    assert result == {"status": "simulated"}
    mock_voice.execute.assert_called_once()


def test_delegate_respects_agent_hint_voice():
    orchestrator = AgentOrchestrator()
    mock_voice = MagicMock()
    mock_voice.execute.return_value = {"status": "simulated"}
    orchestrator.agents["voice"] = mock_voice

    result = orchestrator.delegate("anything", {"agent": "voice", "text": "hi"})

    assert result["status"] == "simulated"
    mock_voice.execute.assert_called_once()


def test_delegate_unknown_agent_hint_adds_warning():
    orchestrator = AgentOrchestrator()
    result = orchestrator.delegate("do something unknown", {"agent": "bogus"})

    assert "error" in result
    assert "orchestrator_warning" in result
    assert "bogus" in result["orchestrator_warning"]


def test_delegate_unknown_task():
    orchestrator = AgentOrchestrator()
    result = orchestrator.delegate("do something unknown")
    assert "error" in result


def test_add_agent():
    orchestrator = AgentOrchestrator()
    mock_agent = MagicMock()
    response = orchestrator.add_agent("test", mock_agent)
    assert response == "Added test agent."
    assert orchestrator.agents["test"] is mock_agent


def test_delegate_uses_added_agent():
    orchestrator = AgentOrchestrator()
    mock_agent = MagicMock()
    mock_agent.execute.return_value = {"status": "custom"}
    orchestrator.add_agent("custom", mock_agent)
    # Direct delegation via add_agent: ensure agent is stored
    assert "custom" in orchestrator.agents
