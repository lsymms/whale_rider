import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.webull.probe import (
    CapabilityProbe,
    HttpRequest,
    HttpResponse,
    WebullClient,
    WebullConfigurationError,
    WebullCredentials,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "webull"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def credentials() -> WebullCredentials:
    return WebullCredentials("production", "app-key", "app-secret", "secret-token")


def test_signed_account_request_uses_only_allowed_headers() -> None:
    captured: list[HttpRequest] = []
    client = WebullClient(
        credentials(),
        transport=lambda request: captured.append(request) or HttpResponse(200, fixture("account-ok.json")),
        now=lambda: datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        nonce=lambda: "a" * 32,
    )
    assert client.get("/trading/accounts/list").status == 200
    request = captured[0]
    assert request.method == "GET"
    assert request.path == "/trading/accounts/list"
    assert request.headers["x-signature"] == "geLOH6fEeef1/PvUUikxav4MTPc="
    assert "app-secret" not in request.headers.values()
    with pytest.raises(ValueError):
        client.get("/trading/orders/place")


def test_missing_credentials_name_only_missing_keys() -> None:
    with pytest.raises(WebullConfigurationError, match="WEBULL_APP_SECRET, WEBULL_ACCESS_TOKEN") as error:
        WebullCredentials.from_local_env({"WEBULL_APP_KEY": "app-key"})
    assert "app-key" not in str(error.value)


def test_probe_distinguishes_data_entitlement_and_redacts_payloads() -> None:
    paths: list[str] = []

    def transport(request: HttpRequest) -> HttpResponse:
        paths.append(request.path)
        if request.path == "/trading/accounts/list":
            return HttpResponse(200, fixture("account-ok.json"))
        return HttpResponse(403, fixture("market-not-subscribed.json"))

    report = CapabilityProbe(WebullClient(credentials(), transport=transport), now=lambda: datetime(2026, 9, 14, 12, 0, tzinfo=UTC)).run()
    body = report.redacted_dict()
    assert paths == [
        "/trading/accounts/list",
        "/market-data/stocks/snapshots/list?symbols=AAPL&category=US_STOCK&extend_hour_required=false&overnight_required=false",
        "/market-data/options/snapshots/list?symbols=AAPL&category=US_OPTION",
    ]
    assert body["capabilities"]["account_read"]["state"] == "verified"
    assert body["capabilities"]["authentication"]["state"] == "verified"
    assert body["capabilities"]["access_token"]["state"] == "verified"
    assert body["capabilities"]["stock_snapshot"]["state"] == "unavailable"
    assert body["capabilities"]["option_snapshot"]["code"] == "MARKET_DATA_NOT_SUBSCRIBED"
    encoded = json.dumps(body)
    assert "redacted-account" not in encoded
    assert "secret-token" not in encoded


def test_invalid_token_stops_data_calls() -> None:
    calls: list[str] = []
    report = CapabilityProbe(
        WebullClient(credentials(), transport=lambda request: calls.append(request.path) or HttpResponse(401, fixture("invalid-token.json")))
    ).run().redacted_dict()
    assert calls == ["/trading/accounts/list"]
    assert report["capabilities"]["account_read"]["code"] == "INVALID_TOKEN"
    assert report["capabilities"]["authentication"]["state"] == "unknown"
    assert report["capabilities"]["access_token"]["state"] == "unavailable"
    assert report["capabilities"]["stock_snapshot"] == {"state": "unknown", "http_status": None, "code": "TOKEN_REQUIRED", "evidence_hash": None}


def test_successful_snapshots_are_verified_without_provider_values() -> None:
    report = CapabilityProbe(WebullClient(credentials(), transport=lambda request: HttpResponse(200, fixture("snapshot-ok.json")))).run()
    assert all(item.state == "verified" for item in report.capabilities.values())
    assert "185.25" not in json.dumps(report.redacted_dict())
