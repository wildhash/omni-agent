"""Tests for MistralClient."""

from unittest.mock import MagicMock, patch

import pytest

from omni_agent.mistral_client import MistralClient


def test_mistral_client_init(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()
    assert client.api_key == "test-key"
    assert "mistral.ai" in client.base_url


def test_generate_code_success(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "def hello(): pass"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = client.generate_code("write a hello function")

    assert result == "def hello(): pass"
    mock_post.assert_called_once()


def test_generate_code_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    import requests as req

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = req.HTTPError("401 Unauthorized")

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(req.HTTPError):
            client.generate_code("write something")


def test_improve_code_calls_generate_code(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    with patch.object(client, "generate_code", return_value="improved code") as mock_gen:
        result = client.improve_code("x = 1", "compute something")

    assert result == "improved code"
    mock_gen.assert_called_once()
    assert "x = 1" in mock_gen.call_args[0][0]
