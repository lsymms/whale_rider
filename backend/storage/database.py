"""SQLite storage setup with ordered, recorded migrations."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class StorageError(RuntimeError):
    pass


class Database:
    def __init__(self, database_path: Path, migration_dir: Path | None = None) -> None:
        self.database_path = database_path
        self.migration_dir = migration_dir or Path(__file__).resolve().parents[2] / "migrations"

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def migrate(self) -> None:
        migrations = sorted(self.migration_dir.glob("[0-9][0-9][0-9]_*.sql"))
        if not migrations:
            raise StorageError(f"No migrations found in {self.migration_dir}")
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            for migration in migrations:
                version = migration.name.split("_", 1)[0]
                if version in applied:
                    continue
                try:
                    connection.executescript(migration.read_text(encoding="utf-8"))
                    connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
                except sqlite3.DatabaseError as error:
                    raise StorageError(f"Migration {migration.name} failed") from error

    def readiness(self) -> bool:
        try:
            with self.connect() as connection:
                connection.execute("SELECT 1 FROM schema_migrations LIMIT 1").fetchone()
            return True
        except sqlite3.DatabaseError:
            return False

