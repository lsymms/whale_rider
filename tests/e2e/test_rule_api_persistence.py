from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def make_client(runtime: Path) -> TestClient:
    return TestClient(create_app(Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=runtime)))


def test_rule_api_revisions_pause_archive_and_restart(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    with make_client(runtime) as client:
        created = client.post("/api/v1/rules", json={"rule_id": "large-nvda", "template": "A01", "minimum_notional": "1000000"})
        assert created.status_code == 201 and created.json()["revision"] == 1
        stale = client.patch("/api/v1/rules/large-nvda", headers={"If-Match": "0"}, json={"rule_id": "large-nvda"})
        assert stale.status_code == 409
        revised = client.patch("/api/v1/rules/large-nvda", headers={"If-Match": "1"}, json={"rule_id": "large-nvda", "template": "A01", "minimum_notional": "2000000"})
        assert revised.status_code == 200 and revised.json()["revision"] == 2
        assert client.post("/api/v1/rules/large-nvda/pause", json={}).json()["state"] == "paused"
        assert client.post("/api/v1/rules/large-nvda/archive").json()["state"] == "archived"
    with make_client(runtime) as restarted:
        saved = restarted.get("/api/v1/rules").json()
    assert saved == [{"rule_id": "large-nvda", "revision": 2, "state": "archived", "paused_until": None, "rule": {"minimum_notional": "2000000", "rule_id": "large-nvda", "template": "A01"}}]
