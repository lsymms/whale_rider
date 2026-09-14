"""FastAPI application factory for the loopback-only local service."""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from backend.api import LocalApiService, router
from backend.config import Settings
from backend.storage import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings.from_env()
    database = Database(configured.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.migrate()
        app.state.database = database
        app.state.settings = configured
        app.state.local_api = LocalApiService()
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
    return app


app = create_app()
