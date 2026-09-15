from datetime import UTC, datetime
from pathlib import Path

from backend.adapters.telegram import TelegramAdapter
from backend.adapters.webull.probe import CapabilityProbe, HttpResponse, WebullClient, WebullCredentials
from backend.workers.capability_report import CapabilityReportWorkflow, sanitize_report


def probe(calls: list[str]) -> CapabilityProbe:
    def transport(request: object) -> HttpResponse:
        calls.append(request.path)
        if request.path == "/openapi/account/list":
            return HttpResponse(200, {"account": {"id": "private-account", "cash": "12345"}})
        return HttpResponse(403, {"code": "MARKET_DATA_NOT_SUBSCRIBED", "detail": "private provider text"})

    client = WebullClient(
        WebullCredentials("production", "app-key", "app-secret", "access-token"),
        transport=transport,
        now=lambda: datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        nonce=lambda: "n" * 32,
    )
    return CapabilityProbe(client, now=lambda: datetime(2026, 9, 14, 12, 0, tzinfo=UTC))


def test_default_workflow_only_runs_read_probe_and_never_uses_telegram() -> None:
    calls: list[str] = []
    sent: list[str] = []
    telegram = TelegramAdapter(lambda *_: sent.append("sent") or "message-id", test_destination_id="test-chat", test_delivery_enabled=True, live_delivery_enabled=False)
    result = CapabilityReportWorkflow(probe(calls), telegram, test_destination_id="test-chat").run()
    assert calls == [
            "/openapi/account/list",
        "/market-data/stocks/snapshots/list?symbols=AAPL&category=US_STOCK&extend_hour_required=false&overnight_required=false",
        "/market-data/options/snapshots/list?symbols=AAPL&category=US_OPTION",
    ]
    assert result.telegram_test_state == "not_requested"
    assert sent == []
    encoded = str(result.report)
    assert "private-account" not in encoded and "12345" not in encoded and "access-token" not in encoded


def test_explicit_test_sends_summary_only_through_guarded_test_adapter() -> None:
    calls: list[str] = []
    messages: list[tuple[str, str]] = []
    telegram = TelegramAdapter(lambda destination, text: messages.append((destination, text)) or "telegram-42", test_destination_id="test-chat", test_delivery_enabled=True, live_delivery_enabled=False)
    result = CapabilityReportWorkflow(probe(calls), telegram, test_destination_id="test-chat").run(send_telegram_test=True)
    assert result.telegram_test_state == "sent"
    assert result.telegram_message_id == "telegram-42"
    assert messages[0][0] == "test-chat"
    assert "capability TEST" in messages[0][1]
    assert "private-account" not in messages[0][1]


def test_sanitizer_drops_unexpected_account_and_secret_fields() -> None:
    report = sanitize_report({
        "environment": "production", "generated_at": "2026-09-14T12:00:00Z",
        "access_token": "must-not-escape",
        "capabilities": {"stock_snapshot": {"state": "verified", "http_status": 200, "account": "private", "raw": {"token": "bad"}}},
    })
    assert report == {"environment": "production", "generated_at": "2026-09-14T12:00:00Z", "capabilities": {"stock_snapshot": {"state": "verified", "http_status": 200}}}
