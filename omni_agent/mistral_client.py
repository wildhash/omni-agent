"""Mistral API client for code generation and improvement."""

import os
import time
from typing import Optional

import requests


class MistralClientError(RuntimeError):
    """Raised when the Mistral API returns an unexpected response."""


class MistralClient:
    """Thin wrapper around the Mistral chat-completions API.

    Methods
    -------
    generate_code(prompt, model, temperature, max_tokens):
        Generate text/code from a free-form prompt.
    improve_code(code, task):
        Ask Mistral to refine an existing code snippet.
    """

    def __init__(self) -> None:
        self.api_key: Optional[str] = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            import warnings
            warnings.warn(
                "MISTRAL_API_KEY is not set. API calls will fail.",
                stacklevel=2,
            )
        self.base_url = "https://api.mistral.ai/v1/"
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _raise_unexpected_shape(self, data: object) -> None:
        raise MistralClientError(f"Unexpected Mistral response shape: {data!r}")

    def generate_code(
        self,
        prompt: str,
        model: str = "mistral-medium",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate code using the Mistral chat-completions endpoint.

        Parameters
        ----------
        prompt:
            User-facing instruction or question.
        model:
            Mistral model identifier.
        temperature:
            Sampling temperature (lower = more deterministic).
        max_tokens:
            Maximum number of tokens to generate.

        Returns
        -------
        str
            The generated text returned by the model.
        """
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{self.base_url}chat/completions"
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=60,
                )
            except requests.exceptions.RequestException:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(0.5 * (2**attempt))
                continue

            status_code = getattr(response, "status_code", 0)
            if not isinstance(status_code, int):
                status_code = 0

            if status_code == 429 or 500 <= status_code <= 599:
                if attempt == max_attempts - 1:
                    response.raise_for_status()
                time.sleep(0.5 * (2**attempt))
                continue

            response.raise_for_status()

            try:
                data = response.json()
            except ValueError as exc:  # pragma: no cover
                body = getattr(response, "text", "")
                raise MistralClientError(
                    f"Failed to decode JSON from Mistral (status={status_code}): {body[:500]}"
                ) from exc

            if not isinstance(data, dict):
                self._raise_unexpected_shape(data)

            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                self._raise_unexpected_shape(data)

            choice0 = choices[0]
            if not isinstance(choice0, dict):
                self._raise_unexpected_shape(data)

            message = choice0.get("message")
            if not isinstance(message, dict):
                self._raise_unexpected_shape(data)

            content = message.get("content")
            if not isinstance(content, str):
                self._raise_unexpected_shape(data)

            return content

        raise AssertionError("unreachable")

    def improve_code(self, code: str, task: str) -> str:
        """Ask Mistral to improve *code* with respect to *task*.

        Parameters
        ----------
        code:
            Existing Python source code to refine.
        task:
            Description of what the code is supposed to do.

        Returns
        -------
        str
            The improved code returned by the model.
        """
        prompt = (
            f"Task: {task}\n"
            f"Current Implementation:\n```python\n{code}\n```\n"
            "Suggest improvements. Return ONLY the improved code, no explanations."
        )
        return self.generate_code(prompt)
