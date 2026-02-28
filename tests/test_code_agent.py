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


def test_execute_python_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OMNI_AGENT_ENABLE_CODE_EXEC", raising=False)
    agent = CodeAgent()
    result = agent.execute("run code", {"code": "print('hello')"})
    assert result["error"].startswith("Code execution is disabled by default")


def test_execute_debug():
    agent = CodeAgent()
    result = agent.execute("debug this code", {"code": "x = 1"})
    assert "analysis" in result
    assert "suggested_fixes" in result


def test_execute_unknown_task():
    agent = CodeAgent()
    result = agent.execute("dance")
    assert "error" in result


def test_containerize_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OMNI_AGENT_ENABLE_DOCKER_BUILD", raising=False)
    agent = CodeAgent()
    result = agent.execute("docker build", {"path": "."})
    assert result["error"].startswith("Docker builds are disabled by default")
