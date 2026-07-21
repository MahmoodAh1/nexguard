"""Ollama LLM provider (local inference only — no cloud APIs).

Implements the :class:`~nexguard.domain.ports.LLMProvider` port by calling a local
Ollama server with ``format=json`` and ``temperature=0`` for deterministic,
schema-shaped output. The response is validated against the requested Pydantic
schema before it can reach application logic; validation failures raise a domain
error rather than propagating malformed data.
"""

from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from nexguard.domain.errors import ReportGenerationError

TModel = TypeVar("TModel", bound=BaseModel)


class OllamaLLMProvider:
    """Calls a local Ollama server's ``/api/generate`` endpoint."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    async def complete_json(self, prompt: str, schema: type[TModel]) -> TModel:
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ReportGenerationError(f"Ollama request failed: {exc}") from exc
        finally:
            if self._owns_client:
                await client.aclose()

        raw = body.get("response", "")
        try:
            return schema.model_validate_json(raw)
        except ValidationError as exc:
            raise ReportGenerationError(
                f"Ollama returned output that does not match {schema.__name__}: {exc}"
            ) from exc
