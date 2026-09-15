import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from backend.adapters.ai.openrouter import (
    TEXT_TIMEOUT_SECONDS,
    VISION_TIMEOUT_SECONDS,
    OpenRouterClient,
    OpenRouterError,
    OpenRouterSettings,
    create_openrouter_explanation_adapter,
    create_openrouter_vision_adapter,
)
from backend.domain.risk.candidates import Candidate, CandidateKind


class Response:
    def __init__(self, body: object, status_code: int = 200) -> None:
        self.body = body
        self.status_code = status_code

    def json(self):
        return self.body


class FakeTransport:
    def __init__(self, response: Response | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def settings() -> OpenRouterSettings:
    return OpenRouterSettings(api_key="test-secret-key", model="provider/configured-model")


def png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + (40).to_bytes(4, "big") + (20).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"


def completion(payload: object) -> Response:
    return Response({"choices": [{"message": {"content": json.dumps(payload)}}]})


def test_settings_reads_configured_provider_model_without_hardcoded_model() -> None:
    active = OpenRouterSettings.from_env({"AI_PROVIDER": "openrouter", "AI_API_KEY": "key", "AI_MODEL": "configured/free-model"})
    assert active.model == "configured/free-model"
    with pytest.raises(ValueError, match="AI_MODEL"):
        OpenRouterSettings.from_env({"AI_PROVIDER": "openrouter", "AI_API_KEY": "key"})


def test_vision_factory_uses_vision_timeout_and_only_server_side_bearer_header() -> None:
    transport = FakeTransport(completion({"schema_version": "ocr-positions-v1", "rows": [{"symbol": "NVDA", "asset_type": "stock", "quantity": "1", "confidence": {"symbol": 1}}], "warnings": []}))
    draft = create_openrouter_vision_adapter(settings(), transport).create_draft(png())
    call = transport.calls[0]
    assert draft.commit_allowed is False and draft.rows[0].symbol == "NVDA"
    assert call["timeout"] == VISION_TIMEOUT_SECONDS
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"] == {"Authorization": "Bearer test-secret-key", "Content-Type": "application/json"}
    body = call["json"]
    assert body["model"] == "provider/configured-model"
    assert "api_key" not in body


def test_explanation_factory_receives_only_opaque_ids_and_uses_text_timeout() -> None:
    transport = FakeTransport(completion({"status": "ranked", "ranked_candidate_ids": ["hold"], "supporting_evidence_ids": ["event-1"], "rationale": "Use the supplied candidate.", "counterevidence": ["Intent unknown."], "conditions": ["Recalculate if inputs change."], "uncertainties": ["No external facts."]}))
    candidate = Candidate("hold", CandidateKind.HOLD, (), Decimal("0"), Decimal("0"), 1, 1, (), datetime(2026, 9, 14, tzinfo=UTC) + timedelta(seconds=60), "wait")
    result = create_openrouter_explanation_adapter(settings(), transport).explain(run_id="run-1", objective="review", candidates=(candidate,), evidence_ids=("event-1",))
    call = transport.calls[0]
    assert result.status == "ranked"
    assert call["timeout"] == TEXT_TIMEOUT_SECONDS
    message = call["json"]["messages"][1]["content"]
    assert "allowed_candidate_ids" in message and "legs" not in message and "quantity" not in message


def test_errors_are_redacted_and_timeout_is_safe() -> None:
    client = OpenRouterClient(settings(), FakeTransport(Response({"error": "test-secret-key"}, 401)))
    with pytest.raises(OpenRouterError) as error:
        client.structured_completion([], timeout=TEXT_TIMEOUT_SECONDS)
    assert str(error.value) == "OpenRouter returned HTTP 401."
    timeout = OpenRouterClient(settings(), FakeTransport(httpx.TimeoutException("test-secret-key")))
    with pytest.raises(OpenRouterError) as error:
        timeout.structured_completion([], timeout=TEXT_TIMEOUT_SECONDS)
    assert str(error.value) == "OpenRouter request timed out."
