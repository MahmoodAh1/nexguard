"""Unit tests for the Ollama provider using a mocked HTTP transport."""

from __future__ import annotations

import httpx
import pytest

from nexguard.domain.errors import ReportGenerationError
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.value_objects import Severity
from nexguard.infrastructure.llm.ollama_provider import OllamaLLMProvider

_VALID_REPORT_JSON = IncidentReportPayload(
    summary="parsed from ollama",
    severity=Severity.MEDIUM,
    confidence="medium",
    recommended_investigation_steps=["inspect the block"],
).model_dump_json()


def _provider(handler: object) -> OllamaLLMProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return OllamaLLMProvider(client=client, model="llama3.1")


async def test_parses_valid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        assert request.headers  # request was actually formed
        return httpx.Response(200, json={"response": _VALID_REPORT_JSON})

    provider = _provider(handler)
    payload = await provider.complete_json("prompt", IncidentReportPayload)

    assert payload.summary == "parsed from ollama"
    assert payload.severity is Severity.MEDIUM


async def test_schema_mismatch_raises_report_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": '{"unexpected": true}'})

    with pytest.raises(ReportGenerationError):
        await _provider(handler).complete_json("prompt", IncidentReportPayload)


async def test_http_error_raises_report_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model not found"})

    with pytest.raises(ReportGenerationError):
        await _provider(handler).complete_json("prompt", IncidentReportPayload)


def test_provider_name_reflects_model() -> None:
    assert OllamaLLMProvider(model="mistral").name == "ollama:mistral"
