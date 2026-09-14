from pathlib import Path

import pytest

from backend.config import ConfigurationError, Settings, load_local_env


def test_uses_host_local_default_runtime_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings = Settings.from_env({"APP_ENV": "test", "APP_HOST": "127.0.0.1", "APP_PORT": "8787"})
    assert settings.runtime_dir == (tmp_path / "WhaleRider").resolve()


def test_local_env_does_not_override_process_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_PORT=9999\nWEBULL_APP_SECRET=never-log-me\n", encoding="utf-8")
    target = {"APP_PORT": "8787"}
    load_local_env(env_file, target)
    assert target == {"APP_PORT": "8787", "WEBULL_APP_SECRET": "never-log-me"}


@pytest.mark.parametrize("values", [
    {"APP_HOST": "0.0.0.0"},
    {"APP_PORT": "0"},
    {"APP_PORT": "bad"},
    {"APP_RUNTIME_DIR": r"\\server\share\whale-rider"},
])
def test_rejects_unsafe_settings(values: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env(values)
