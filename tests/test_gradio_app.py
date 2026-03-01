"""Tests for the Gradio UI helpers.

These tests avoid importing Gradio itself; they only validate the JSON context
parsing logic used by the UI.
"""

from omni_agent.ui.gradio_app import _parse_context


def test_parse_context_empty():
    ctx, err = _parse_context("")
    assert ctx == {}
    assert err is None


def test_parse_context_valid_object():
    ctx, err = _parse_context('{"agent": "web"}')
    assert err is None
    assert ctx == {"agent": "web"}


def test_parse_context_invalid_json():
    ctx, err = _parse_context("{invalid}")
    assert ctx == {}
    assert err is not None


def test_parse_context_requires_object():
    ctx, err = _parse_context('[{"agent": "web"}]')
    assert ctx == {}
    assert err is not None
