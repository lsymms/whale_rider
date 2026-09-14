from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def test_health_migrates_and_reports_database_ready(tmp_path: Path) -> None:
    settings = Settings(environment="test", host="127.0.0.1", port=8787, runtime_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "whale-rider",
            "version": "0.1.0",
            "database": "ready",
        }
