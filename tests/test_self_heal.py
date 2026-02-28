"""Tests for SelfHealer."""

from unittest.mock import MagicMock, patch

from omni_agent.self_heal import SelfHealer


def _make_healer():
    orchestrator = MagicMock()
    return SelfHealer(orchestrator)


def test_monitor_unfixable():
    healer = _make_healer()
    diagnosis = {
        "error_type": "CodeError",
        "root_cause": "division by zero",
        "fixable": False,
    }
    with patch.object(healer, "_diagnose_error", return_value=diagnosis):
        result = healer.monitor("run code", {}, ZeroDivisionError("oops"))

    assert result["status"] == "unfixable"
    assert "error" in result


def test_monitor_fixable_new_agent(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_SELF_MODIFY", "1")
    healer = _make_healer()
    diagnosis = {
        "error_type": "MissingAgent",
        "root_cause": "agent not found",
        "fixable": True,
        "suggested_fix": {
            "type": "new_agent",
            "details": "missing VoiceAgent",
            "agent_type": "Voice",
            "code_snippet": "",
        },
    }
    with patch.object(healer, "_diagnose_error", return_value=diagnosis):
        with patch.object(
            healer.agent_generator,
            "register_agent",
            return_value={"status": "success"},
        ):
            result = healer.monitor("voice task", {}, RuntimeError("no agent"))

    assert result["status"] == "fixed"
    assert result["action"] == "generated_new_agent"


def test_diagnose_error_parses_json():
    healer = _make_healer()
    diagnosis_json = (
        '{"error_type": "APIFailure", "root_cause": "timeout", "fixable": false, '
        '"suggested_fix": {"type": "config_update", "details": "", "code_snippet": ""}}'
    )
    fenced = (
        "Some prose with braces {not json}.\n"
        "Here's the JSON:\n"
        "```json\n"
        f"{diagnosis_json}\n"
        "```\n"
    )

    with patch.object(healer.mistral, "generate_code", return_value=fenced):
        result = healer._diagnose_error("task", {}, "Traceback...")

    assert result["error_type"] == "APIFailure"
    assert result["fixable"] is False


def test_diagnose_error_handles_invalid_json():
    healer = _make_healer()
    with patch.object(healer.mistral, "generate_code", return_value="not valid json"):
        result = healer._diagnose_error("task", {}, "trace")

    assert result["error_type"] == "DiagnosisFailed"
    assert result["fixable"] is False


def test_apply_fix_config_update(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_SELF_MODIFY", "1")
    healer = _make_healer()
    diagnosis = {
        "fixable": True,
        "suggested_fix": {"type": "config_update", "details": "", "code_snippet": ""},
    }
    result = healer._apply_fix(diagnosis)
    assert result["status"] == "not_implemented"


def test_apply_fix_unknown_type(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_SELF_MODIFY", "1")
    healer = _make_healer()
    diagnosis = {
        "fixable": True,
        "suggested_fix": {"type": "unknown", "details": "", "code_snippet": ""},
    }
    result = healer._apply_fix(diagnosis)
    assert result["status"] == "unknown_fix_type"


def test_apply_fix_new_agent_empty_details(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_SELF_MODIFY", "1")
    healer = _make_healer()
    diagnosis = {
        "fixable": True,
        "suggested_fix": {"type": "new_agent", "details": "", "agent_type": "", "code_snippet": ""},
    }
    result = healer._apply_fix(diagnosis)
    assert result["status"] == "failed"
    assert "agent type" in result["error"].lower()


def test_apply_fix_code_change_empty_details(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_SELF_MODIFY", "1")
    healer = _make_healer()
    diagnosis = {
        "fixable": True,
        "suggested_fix": {"type": "code_change", "details": "", "code_snippet": ""},
    }
    result = healer._apply_fix(diagnosis)
    assert result["status"] == "failed"
    assert "file path" in result["error"].lower()


def test_apply_fix_code_change_path_traversal(monkeypatch):
    monkeypatch.setenv("OMNI_AGENT_ENABLE_SELF_MODIFY", "1")
    healer = _make_healer()
    diagnosis = {
        "fixable": True,
        "suggested_fix": {
            "type": "code_change",
            "file_path": "/etc/passwd",
            "code_snippet": "malicious",
        },
    }
    result = healer._apply_fix(diagnosis)
    assert result["status"] == "failed"
    assert "relative" in result["error"].lower() or "unsafe" in result["error"].lower()
