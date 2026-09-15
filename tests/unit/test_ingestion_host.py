from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


@dataclass
class StockResult:
    appended_events: int = 0


@dataclass
class OptionResult:
    polled_contracts: int = 0


class FakeOperations:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def consume_stock_batch(self, symbols, max_messages):
        self.calls.append(("stock", tuple(symbols), max_messages))
        return StockResult()

    def poll_options(self, contracts):
        self.calls.append(("options", tuple(contract.instrument_id for contract in contracts)))
        return OptionResult()


def settings(tmp_path: Path) -> Settings:
    return Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=tmp_path / "runtime")


def test_host_starts_idle_and_default_start_fails_without_live_operations(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path))) as client:
        initial = client.get("/api/v1/ingestion/status")
        start = client.post("/api/v1/ingestion/start", json={"stock_symbols": ["NVDA"], "option_contracts": []})
    assert initial.json()["state"] == "stopped"
    assert start.status_code == 422
    assert "not configured" in start.json()["detail"]["message"]


def test_injected_host_operations_remain_idle_until_explicit_start_and_stop(tmp_path: Path) -> None:
    operations = FakeOperations()
    with TestClient(create_app(settings(tmp_path), ingestion_operations=operations)) as client:
        assert operations.calls == []
        started = client.post("/api/v1/ingestion/start", json={"stock_symbols": ["nvda"], "option_contracts": [{"instrument_id": "NVDA-C", "underlying": "NVDA"}]})
        assert started.status_code == 200 and started.json()["state"] == "running"
        assert operations.calls == []
        stopped = client.post("/api/v1/ingestion/stop")
        status = client.get("/api/v1/ingestion/status")
    assert stopped.json()["state"] == "stopped"
    assert status.json()["state"] == "stopped"
    assert operations.calls == []
