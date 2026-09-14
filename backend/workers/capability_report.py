"""Read-only Webull capability report workflow with opt-in Telegram TEST output."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.adapters.telegram import TelegramAdapter
from backend.adapters.webull.probe import CapabilityProbe
from backend.domain.notifications import DeliveryKind, Notification


@dataclass(frozen=True, slots=True)
class CapabilityWorkflowResult:
    report: dict[str, object]
    telegram_test_state: str
    telegram_message_id: str | None = None


class CapabilityReportWorkflow:
    """Runs only allowlisted read probes; it never reads orders or submits broker actions."""

    def __init__(self, probe: CapabilityProbe, telegram: TelegramAdapter | None = None, *, test_destination_id: str | None = None) -> None:
        self._probe = probe
        self._telegram = telegram
        self._test_destination_id = test_destination_id

    def run(self, *, send_telegram_test: bool = False) -> CapabilityWorkflowResult:
        report = sanitize_report(self._probe.run().redacted_dict())
        if not send_telegram_test:
            return CapabilityWorkflowResult(report, "not_requested")
        if self._telegram is None or not self._test_destination_id:
            raise ValueError("Telegram TEST requires an injected guarded adapter and test destination")
        now = datetime.now(UTC)
        message = self._telegram.deliver(
            Notification(
                notification_id=str(uuid4()),
                idempotency_key=f"capability-test-{uuid4()}",
                kind=DeliveryKind.TEST,
                destination_id=self._test_destination_id,
                text=telegram_summary(report),
                created_at=now,
                expires_at=now + timedelta(minutes=5),
            )
        )
        return CapabilityWorkflowResult(report, "sent", message)


def sanitize_report(raw: dict[str, Any]) -> dict[str, object]:
    """Keep only status metadata; reject provider values, account data, and secrets."""
    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("capability report is missing capabilities")
    safe_capabilities: dict[str, object] = {}
    for name, capability in capabilities.items():
        if not isinstance(name, str) or not isinstance(capability, dict):
            raise ValueError("capability report has invalid entries")
        safe_capabilities[name] = {
            key: capability.get(key)
            for key in ("state", "http_status", "code", "evidence_hash")
            if capability.get(key) is not None
        }
    environment = raw.get("environment")
    generated_at = raw.get("generated_at")
    if not isinstance(environment, str) or not isinstance(generated_at, str):
        raise ValueError("capability report is missing metadata")
    return {"environment": environment, "generated_at": generated_at, "capabilities": safe_capabilities}


def telegram_summary(report: dict[str, object]) -> str:
    capabilities = report["capabilities"]
    assert isinstance(capabilities, dict)
    lines = ["Whale Rider capability TEST", f"Environment: {report['environment']}"]
    for name in ("authentication", "access_token", "stock_snapshot", "option_snapshot"):
        item = capabilities.get(name)
        if isinstance(item, dict):
            code = f" ({item['code']})" if item.get("code") else ""
            lines.append(f"{name}: {item.get('state', 'unknown')}{code}")
    lines.append("Read-only probe; no brokerage orders were submitted.")
    return "\n".join(lines)
