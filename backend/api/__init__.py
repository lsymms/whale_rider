"""Loopback REST API backed by deterministic local services."""

from .routes import router
from .service import LocalApiService

__all__ = ["LocalApiService", "router"]
