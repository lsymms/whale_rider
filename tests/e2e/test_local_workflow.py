"""End-to-end local API workflow: all data remains in FastAPI's in-process fake facade."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def _client(runtime_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=runtime_dir)))


def _stock_row(*, needs_review: bool = False) -> dict[str, object]:
    return {
        "instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock", "quantity": "100",
        "underlying_price": "150", "requires_review": ["quantity"] if needs_review else [],
    }


def test_local_operator_workflow_from_health_to_deterministic_suggestion(tmp_path: Path) -> None:
    rule = {
        "rule_id": "stock-large", "template": "A01", "asset_type": "stock", "universe": ["NVDA"],
        "minimum_quantity": "10000", "minimum_notional": "1000000",
    }
    event = {
        "event_id": "execution-1", "instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock",
        "event_type": "execution", "event_time": "2026-09-14T14:30:00Z", "quantity": "10000", "price": "100",
        "identity_reliable": True,
    }
    with _client(tmp_path) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["database"] == "ready"

        dry_run = client.post("/api/v1/rules/simulate", json={"rule": rule, "event": event})
        assert dry_run.status_code == 200
        assert dry_run.json() == {"mode": "dry_run", "code": "triggered", "triggered": True, "notional": "1000000", "enrichment_only": False}

        draft = client.post("/api/v1/imports", json={"account_id": "demo", "source": "ocr", "rows": [_stock_row(needs_review=True)]})
        assert draft.status_code == 202
        draft_id = draft.json()["import_id"]
        assert draft.json()["status"] == "review_required"
        blocked = client.post(f"/api/v1/imports/{draft_id}/commit")
        assert blocked.status_code == 422
        assert blocked.json()["detail"]["message"] == "draft has unresolved review fields"

        reviewed = client.patch(f"/api/v1/imports/{draft_id}/rows", json={"rows": [_stock_row()]})
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "ready_for_commit"
        committed = client.post(f"/api/v1/imports/{draft_id}/commit")
        assert committed.status_code == 200
        assert committed.json()["version"] == 1

        exposure = client.get("/api/v1/positions/demo/exposure")
        assert exposure.status_code == 200
        assert exposure.json()["is_complete"] is True
        assert exposure.json()["by_underlying"] == [{
            "underlying": "NVDA", "known_delta_shares": "100", "gross_known_delta_shares": "100",
            "net_delta_dollars": "15000", "gross_delta_dollars": "15000", "is_complete": True,
            "unknown_instrument_ids": [],
        }]

        suggestions = client.post("/api/v1/suggestions", json={"account_id": "demo"})
        assert suggestions.status_code == 200
        assert suggestions.json()["status"] == "deterministic_candidates"
        assert suggestions.json()["candidates"] == [
            {"id": "hold", "action": "hold", "snapshot_version": 1},
            {"id": "reduce-NVDA", "action": "reduce", "instrument_id": "NVDA", "side": "sell", "quantity": "50", "snapshot_version": 1},
        ]


def test_partial_import_omission_does_not_clear_existing_holdings(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        initial = client.post("/api/v1/imports", json={"account_id": "demo", "source": "manual", "rows": [_stock_row(), {**_stock_row(), "instrument_id": "AMD", "underlying": "AMD", "quantity": "25"}]}).json()
        assert client.post(f"/api/v1/imports/{initial['import_id']}/commit").status_code == 200
        update = client.post("/api/v1/imports", json={"account_id": "demo", "source": "ocr", "expected_position_version": 1, "rows": [{**_stock_row(), "quantity": "150"}]}).json()
        committed = client.post(f"/api/v1/imports/{update['import_id']}/commit")
    assert committed.status_code == 200
    assert {position["instrument_id"]: position["quantity"] for position in committed.json()["positions"]} == {"AMD": "25", "NVDA": "150"}
