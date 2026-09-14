from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def client(tmp_path: Path) -> TestClient:
    settings = Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=tmp_path)
    return TestClient(create_app(settings))


def stock_row(*, review: bool = False) -> dict[str, object]:
    return {
        "instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock", "quantity": "100",
        "underlying_price": "150", "requires_review": ["quantity"] if review else [],
    }


def test_capabilities_is_local_unknown_without_provider_probe(tmp_path: Path) -> None:
    with client(tmp_path) as test_client:
        response = test_client.get("/api/v1/capabilities")
    assert response.status_code == 200
    assert response.json()["source"] == "local_fallback"
    assert response.json()["capabilities"]["option_snapshot"]["state"] == "unknown"


def test_rule_dry_run_is_execution_only_and_never_sends(tmp_path: Path) -> None:
    payload = {
        "rule": {"rule_id": "demo", "template": "A01", "asset_type": "stock", "universe": ["NVDA"], "minimum_quantity": "10000", "minimum_notional": "1000000"},
        "event": {"event_id": "e-1", "instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock", "event_type": "execution", "event_time": "2026-09-14T14:30:00Z", "quantity": "10000", "price": "100", "identity_reliable": True},
    }
    with client(tmp_path) as test_client:
        response = test_client.post("/api/v1/rules/simulate", json=payload)
    assert response.status_code == 200
    assert response.json() == {"mode": "dry_run", "code": "triggered", "triggered": True, "notional": "1000000", "enrichment_only": False}


def test_review_blocks_commit_then_reviewed_draft_commits_and_exposes_candidates(tmp_path: Path) -> None:
    with client(tmp_path) as test_client:
        created = test_client.post("/api/v1/imports", json={"account_id": "demo", "source": "ocr", "rows": [stock_row(review=True)]})
        assert created.status_code == 202
        import_id = created.json()["import_id"]
        assert test_client.post(f"/api/v1/imports/{import_id}/commit").status_code == 422
        reviewed = test_client.patch(f"/api/v1/imports/{import_id}/rows", json={"rows": [stock_row()]})
        assert reviewed.json()["status"] == "ready_for_commit"
        committed = test_client.post(f"/api/v1/imports/{import_id}/commit")
        assert committed.status_code == 200 and committed.json()["version"] == 1
        exposure = test_client.get("/api/v1/positions/demo/exposure")
        assert exposure.json()["by_underlying"][0]["net_delta_dollars"] == "15000"
        suggestions = test_client.post("/api/v1/suggestions", json={"account_id": "demo"})
    assert suggestions.json()["status"] == "deterministic_candidates"
    assert suggestions.json()["candidates"][1]["quantity"] == "50"


def test_incomplete_exposure_abstains_from_suggestions(tmp_path: Path) -> None:
    row = {"instrument_id": "NVDA-C", "underlying": "NVDA", "asset_type": "option", "quantity": "1", "multiplier": "100"}
    with client(tmp_path) as test_client:
        created = test_client.post("/api/v1/imports", json={"account_id": "demo", "source": "manual", "rows": [row]}).json()
        test_client.post(f"/api/v1/imports/{created['import_id']}/commit")
        response = test_client.post("/api/v1/suggestions", json={"account_id": "demo"})
    assert response.json() == {"status": "abstain", "reason": "exposure_incomplete", "snapshot_version": 1, "candidates": []}
