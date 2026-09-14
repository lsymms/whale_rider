"""Draft-only OCR job entrypoint; persistence and position commits stay elsewhere."""
from __future__ import annotations

from backend.adapters.ai.vision import DraftImport, VisionOcrAdapter


class ImportWorker:
    def __init__(self, vision: VisionOcrAdapter) -> None:
        self._vision = vision

    def create_ocr_draft(self, image_bytes: bytes) -> DraftImport:
        """Return an uncommittable draft for explicit human review."""
        return self._vision.create_draft(image_bytes)
