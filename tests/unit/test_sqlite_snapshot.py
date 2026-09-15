import importlib.util
import sqlite3
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[2] / "scripts" / "sqlite_snapshot.py"
SPEC = importlib.util.spec_from_file_location("sqlite_snapshot", SCRIPT)
assert SPEC and SPEC.loader
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


def create_database(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE items (value TEXT NOT NULL)")
        connection.execute("INSERT INTO items VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def values(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("SELECT value FROM items ORDER BY rowid")]
    finally:
        connection.close()


def test_backup_uses_sqlite_api_writes_hash_and_preserves_source(tmp_path: Path) -> None:
    source = tmp_path / "runtime" / "whale-rider.sqlite3"
    source.parent.mkdir()
    create_database(source, "before")
    destination = tmp_path / "backups" / "whale-rider-20260915T010101Z.sqlite3"
    snapshot.backup(source, destination)
    assert values(source) == ["before"]
    assert values(destination) == ["before"]
    assert destination.with_suffix(".sqlite3.sha256").read_text(encoding="ascii").endswith(f"  {destination.name}\n")


def test_restore_requires_force_and_retains_previous_database(tmp_path: Path) -> None:
    backup = tmp_path / "backup.sqlite3"
    create_database(backup, "restored")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    destination = runtime / "whale-rider.sqlite3"
    create_database(destination, "current")
    with pytest.raises(snapshot.SnapshotError, match="--force"):
        snapshot.restore(backup, destination, False)
    snapshot.restore(backup, destination, True)
    assert values(destination) == ["restored"]
    previous = list(runtime.glob("whale-rider.pre-restore-*.sqlite3"))
    assert len(previous) == 1 and values(previous[0]) == ["current"]


def test_backup_does_not_overwrite_an_explicit_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "existing.sqlite3"
    create_database(source, "one")
    create_database(destination, "two")
    with pytest.raises(snapshot.SnapshotError, match="already exists"):
        snapshot.backup(source, destination)
    assert values(destination) == ["two"]
