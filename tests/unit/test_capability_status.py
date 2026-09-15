from backend.api.service import LocalApiService
from backend.app import create_app
from backend.config import Settings
from backend.workers.capabilities import CapabilityProbeRunner
from fastapi.testclient import TestClient


class FakeReport:
    def redacted_dict(self):
        return {
            "environment": "production",
            "generated_at": "2026-09-15T14:30:00Z",
            "capabilities": {"stock_snapshot": {"state": "unavailable", "code": "MARKET_DATA_NOT_SUBSCRIBED"}},
        }


class FakeProbe:
    def __init__(self):
        self.calls = 0

    def run(self):
        self.calls += 1
        return FakeReport()


def test_probe_is_operator_triggered_and_status_only_contains_redacted_report() -> None:
    probe = FakeProbe()
    service = LocalApiService(CapabilityProbeRunner(lambda: probe))
    assert service.capabilities()["source"] == "local_fallback"
    report = service.refresh_capabilities()
    assert probe.calls == 1
    assert report["source"] == "operator_probe"
    assert report["capabilities"]["stock_snapshot"]["code"] == "MARKET_DATA_NOT_SUBSCRIBED"
    assert service.capabilities() == report


def test_invalid_probe_result_is_rejected_before_becoming_service_status() -> None:
    class InvalidProbe:
        def run(self):
            return object()

    service = LocalApiService(CapabilityProbeRunner(lambda: InvalidProbe()))
    try:
        service.refresh_capabilities()
    except ValueError as error:
        assert "invalid redacted report" in str(error)
    else:
        raise AssertionError("invalid report was accepted")
    assert service.capabilities()["source"] == "local_fallback"


def test_operator_endpoint_refreshes_status_without_probe_on_startup(tmp_path) -> None:
    probe = FakeProbe()
    settings = Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        client.app.state.local_api = LocalApiService(CapabilityProbeRunner(lambda: probe))
        assert probe.calls == 0
        assert client.get("/api/v1/capabilities").json()["source"] == "local_fallback"
        response = client.post("/api/v1/capabilities/probe")
    assert response.status_code == 200 and response.json()["source"] == "operator_probe"
    assert probe.calls == 1
