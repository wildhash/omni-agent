"""Mistral API client for code generation and improvement."""

import os
from typing import Optional

import requests


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
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
        response = requests.post(
            f"{self.base_url}chat/completions",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

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
