"""Validated local-only service configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised before the service opens storage or starts listening."""


def _local_app_data() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "WhaleRider" if base else Path.home() / ".local" / "share" / "whale-rider"


def load_local_env(env_file: Path | None = None, environ: dict[str, str] | None = None) -> None:
    """Load simple KEY=VALUE entries without replacing explicit process settings."""
    target = os.environ if environ is None else environ
    source = env_file or Path(__file__).resolve().parents[1] / ".env"
    if not source.is_file():
        return
    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "").isalnum():
            target.setdefault(key, value.strip().strip("\"'"))


def _is_network_path(path: Path) -> bool:
    """Reject UNC and mapped network drives where SQLite WAL is unsafe."""
    raw = str(path)
    if raw.startswith("\\\\") or raw.startswith("//"):
        return True
    if os.name != "nt" or not path.drive:
        return False
    try:
        import ctypes

        DRIVE_REMOTE = 4
        return ctypes.windll.kernel32.GetDriveTypeW(f"{path.drive}\\") == DRIVE_REMOTE
    except (AttributeError, OSError):
        # A failed platform probe must not quietly approve an explicitly UNC path;
        # mapped-drive detection is best effort when the Win32 API is unavailable.
        return False


@dataclass(frozen=True)
class Settings:
    environment: str
    host: str
    port: int
    runtime_dir: Path

    @property
    def database_path(self) -> Path:
        return self.runtime_dir / "whale-rider.sqlite3"

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> "Settings":
        if values is None:
            load_local_env()
        source = os.environ if values is None else values
        environment = source.get("APP_ENV", "development").strip().lower()
        if environment not in {"development", "test", "production"}:
            raise ConfigurationError("APP_ENV must be development, test, or production.")
        host = source.get("APP_HOST", "127.0.0.1").strip()
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ConfigurationError("APP_HOST must be a loopback address for the local service.")
        try:
            port = int(source.get("APP_PORT", "8787"))
        except ValueError as error:
            raise ConfigurationError("APP_PORT must be an integer.") from error
        if not 1 <= port <= 65535:
            raise ConfigurationError("APP_PORT must be between 1 and 65535.")
        raw_runtime = source.get("APP_RUNTIME_DIR", "").strip()
        runtime_dir = Path(raw_runtime).expanduser() if raw_runtime else _local_app_data()
        if _is_network_path(runtime_dir):
            raise ConfigurationError("APP_RUNTIME_DIR must be a host-local path; network filesystems are unsafe for SQLite WAL.")
        return cls(environment=environment, host=host, port=port, runtime_dir=runtime_dir.resolve())
