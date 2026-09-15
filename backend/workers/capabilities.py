"""Operator-triggered, read-only capability probing."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class RedactedProbe(Protocol):
    def run(self) -> Any: ...


class CapabilityProbeRunner:
    """Creates Webull network clients only when an operator explicitly invokes run."""

    def __init__(self, factory: Callable[[], RedactedProbe] | None = None) -> None:
        self._factory = factory or self._production_probe

    def run(self) -> dict[str, object]:
        report = self._factory().run()
        redacted = getattr(report, "redacted_dict", None)
        if not callable(redacted):
            raise ValueError("capability probe returned an invalid redacted report")
        payload = redacted()
        if not isinstance(payload, dict) or not isinstance(payload.get("capabilities"), dict):
            raise ValueError("capability probe returned an invalid redacted report")
        return {"source": "operator_probe", **payload}

    @staticmethod
    def _production_probe() -> RedactedProbe:
        # This import is deliberately deferred: app startup makes no Webull calls
        # and does not require Webull credentials to be present.
        from backend.adapters.webull.probe import CapabilityProbe, WebullClient, WebullCredentials

        return CapabilityProbe(WebullClient(WebullCredentials.from_local_env()))
