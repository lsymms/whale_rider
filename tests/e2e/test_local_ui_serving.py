from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def app_with_ui(tmp_path: Path) -> TestClient:
    ui = tmp_path / "ui"
    assets = ui / "assets"
    assets.mkdir(parents=True)
    (ui / "index.html").write_text("<main id='root'>Whale Rider UI</main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('local-ui')", encoding="utf-8")
    settings = Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=tmp_path / "runtime")
    return TestClient(create_app(settings, frontend_dir=ui))


def test_serves_built_spa_and_preserves_api_routes(tmp_path: Path) -> None:
    with app_with_ui(tmp_path) as client:
        root = client.get("/")
        deep_link = client.get("/positions")
        asset = client.get("/assets/app.js")
        health = client.get("/api/v1/health")
    assert root.status_code == 200 and "Whale Rider UI" in root.text
    assert root.headers["cache-control"] == "no-store"
    assert deep_link.status_code == 200 and deep_link.text == root.text
    assert asset.status_code == 200 and "local-ui" in asset.text
    assert asset.headers["x-content-type-options"] == "nosniff"
    assert health.status_code == 200 and health.json()["service"] == "whale-rider"


def test_does_not_turn_missing_assets_or_unknown_api_paths_into_spa_routes(tmp_path: Path) -> None:
    with app_with_ui(tmp_path) as client:
        missing_asset = client.get("/assets/missing.js")
        missing_api = client.get("/api/v1/not-a-route")
        escaped = client.get("/%2e%2e/secret.txt")
    assert missing_asset.status_code == 404
    assert missing_api.status_code == 404
    assert escaped.status_code == 404


def test_reports_missing_ui_build_without_affecting_health_api(tmp_path: Path) -> None:
    settings = Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=tmp_path / "runtime")
    with TestClient(create_app(settings, frontend_dir=tmp_path / "not-built")) as client:
        page = client.get("/")
        health = client.get("/api/v1/health")
    assert page.status_code == 503
    assert "UI build not found" in page.text
    assert health.status_code == 200
