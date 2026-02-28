"""Tests for MistralClient."""

from unittest.mock import MagicMock, patch

import pytest

from omni_agent.mistral_client import MistralClient, MistralClientError


def test_mistral_client_init(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()
    assert client.api_key == "test-key"
    assert "mistral.ai" in client.base_url
    assert client.headers["Authorization"] == "Bearer test-key"


def test_mistral_client_init_without_api_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.warns(UserWarning, match="MISTRAL_API_KEY"):
        client = MistralClient()
    assert "Authorization" not in client.headers


def test_generate_code_success(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
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
    mock_response.status_code = 401
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


def test_generate_code_raises_on_unexpected_response_shape(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"not_choices": []}
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(MistralClientError, match="Unexpected Mistral response shape"):
            client.generate_code("write something")


def test_generate_code_retries_on_429(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.raise_for_status.side_effect = Exception("rate limited")

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    ok.raise_for_status = MagicMock()

    with patch("requests.post", side_effect=[rate_limited, ok]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            result = client.generate_code("write something")

    assert result == "ok"
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once()

def test_generate_code_retries_on_5xx(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    client = MistralClient()

    server_error = MagicMock()
    server_error.status_code = 500
    server_error.raise_for_status.side_effect = Exception("server error")

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    ok.raise_for_status = MagicMock()

    with patch("requests.post", side_effect=[server_error, ok]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            result = client.generate_code("write something")

    assert result == "ok"
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once()
