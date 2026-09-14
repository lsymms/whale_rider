import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.ai.vision import ImageValidationError, OcrSchemaError, VisionOcrAdapter, validate_image
from backend.workers.imports import ImportWorker


FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai" / "valid-ocr-response.json"


def png(width: int = 40, height: int = 20, extra: bytes = b"") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + extra


class FakeVision:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls = 0

    def extract_positions(self, image, schema):
        self.calls += 1
        assert schema["strict"] is True
        assert image.media_type == "image/png"
        return self.payload


def test_valid_image_and_ocr_result_produces_review_required_draft() -> None:
    provider = FakeVision(json.loads(FIXTURE.read_text(encoding="utf-8")))
    adapter = VisionOcrAdapter(provider, "openai/gpt-5.6-luna", now=lambda: datetime(2026, 9, 14, 12, tzinfo=UTC))
    draft = ImportWorker(adapter).create_ocr_draft(png(400, 100))
    assert provider.calls == 1
    assert draft.status == "review_required"
    assert draft.source == "ocr"
    assert draft.commit_allowed is False
    assert draft.image_media_type == "image/png"
    assert draft.rows[0].quantity == 100
    assert draft.rows[1].option_right == "call"
    assert draft.rows[1].option_strike == 200


@pytest.mark.parametrize("payload", [b"not-an-image", b"\x89PNG\r\n\x1a\n" + b"bad", png(5001, 5001), png(extra=b"acTL")])
def test_invalid_or_unsafe_images_never_reach_provider(payload: bytes) -> None:
    with pytest.raises(ImageValidationError):
        validate_image(payload)


def test_rejects_unsupported_provider_fields_and_never_marks_draft_committable() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["rows"][0]["broker_instruction"] = "send order"
    with pytest.raises(OcrSchemaError, match="unsupported fields"):
        VisionOcrAdapter(FakeVision(payload), "test-model").create_draft(png())


def test_rejects_float_quantities_and_incomplete_option_identity() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["rows"][0]["quantity"] = 100
    with pytest.raises(OcrSchemaError, match="decimal string"):
        VisionOcrAdapter(FakeVision(payload), "test-model").create_draft(png())


def test_rejects_bounding_boxes_outside_the_uploaded_image() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["rows"][0]["bounding_box"]["width"] = 500
    with pytest.raises(OcrSchemaError, match="within the uploaded image"):
        VisionOcrAdapter(FakeVision(payload), "test-model").create_draft(png(400, 100))
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del payload["rows"][1]["option"]["expiry"]
    with pytest.raises(OcrSchemaError, match="YYYY-MM-DD"):
        VisionOcrAdapter(FakeVision(payload), "test-model").create_draft(png())


def test_enforces_image_byte_limit_before_provider_call() -> None:
    provider = FakeVision({})
    with pytest.raises(ImageValidationError, match="byte limit"):
        VisionOcrAdapter(provider, "test-model").create_draft(png(extra=b"x" * (10 * 1024 * 1024)))
    assert provider.calls == 0
