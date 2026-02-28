"""Tests for CodeAgent."""

from omni_agent.agents.code_agent import CodeAgent


def test_execute_python_hello(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_CODE_EXEC", "1")
    agent = CodeAgent()
    result = agent.execute("run code", {"code": "print('hello')"})
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


def test_execute_python_no_code():
    agent = CodeAgent()
    result = agent.execute("run code", {})
    assert "error" in result


def test_execute_debug():
    agent = CodeAgent()
    result = agent.execute("debug this code", {"code": "x = 1"})
    assert "analysis" in result
    assert "suggested_fixes" in result


def test_execute_unknown_task():
    agent = CodeAgent()
    result = agent.execute("dance")
    assert "error" in result
