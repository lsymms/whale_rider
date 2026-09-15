"""FastAPI application factory for the loopback-only local service."""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response

from backend.api import LocalApiService, router
from backend.config import Settings
from backend.storage import Database
from backend.workers.ingestion_lifecycle import IngestionLifecycle, IngestionOperations


def create_app(
    settings: Settings | None = None,
    frontend_dir: Path | None = None,
    ingestion_operations: IngestionOperations | None = None,
) -> FastAPI:
    configured = settings or Settings.from_env()
    database = Database(configured.database_path)
    configured_ui = os.environ.get("APP_FRONTEND_DIR")
    ui_root = (frontend_dir if frontend_dir is not None else Path(configured_ui) if configured_ui else Path(__file__).resolve().parents[1] / "frontend" / "dist").resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.migrate()
        app.state.database = database
        app.state.settings = configured
        # No production transport is constructed here. The host may inject a
        # read-only operation set for an explicit operator start request.
        app.state.local_api = LocalApiService(ingestion=IngestionLifecycle(ingestion_operations))
        yield

    app = FastAPI(title="Whale Rider", version="0.1.0", lifespan=lifespan)

    @app.get("/api/v1/health")
    async def health(request: Request) -> dict[str, object]:
        db: Database = request.app.state.database
        return {
            "status": "ok" if db.readiness() else "degraded",
            "service": "whale-rider",
            "version": "0.1.0",
            "database": "ready" if db.readiness() else "unavailable",
        }

    @app.get("/api/v1/config")
    async def config(request: Request) -> dict[str, object]:
        # Deliberately expose only non-secret, operational values.
        current: Settings = request.app.state.settings
        return {"environment": current.environment, "host": current.host, "port": current.port}

    app.include_router(router)

    @app.get("/", include_in_schema=False, response_model=None)
    @app.get("/{frontend_path:path}", include_in_schema=False, response_model=None)
    async def frontend(frontend_path: str = "") -> Response:
        """Serve a pre-built SPA without exposing files outside its build directory."""
        index = ui_root / "index.html"
        if not index.is_file():
            return PlainTextResponse("UI build not found. Run scripts/start.ps1 to build the local frontend.", status_code=503)
        if frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = (ui_root / frontend_path).resolve()
        try:
            candidate.relative_to(ui_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Not found") from error
        if frontend_path and candidate.is_file():
            return FileResponse(candidate, headers={"X-Content-Type-Options": "nosniff"})
        if frontend_path and Path(frontend_path).suffix:
            raise HTTPException(status_code=404, detail="Static asset not found")
        return FileResponse(index, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
    return app


app = create_app()
