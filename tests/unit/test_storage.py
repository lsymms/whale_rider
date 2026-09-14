from pathlib import Path

from backend.storage import Database


def test_migrations_are_idempotent_and_persist(tmp_path: Path) -> None:
    database = Database(tmp_path / "runtime" / "whale-rider.sqlite3")
    database.migrate()
    database.migrate()
    with database.connect() as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert versions == ["001"]
    assert {"settings", "capability_reports", "audit_events"} <= tables
    assert database.readiness()

